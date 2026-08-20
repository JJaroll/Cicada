"""Tests de cicada/ipod/device/write_guard — la pieza central de la Fase 0.

Todo con tmp_path simulando el árbol del iPod; ningún dispositivo real.
"""
import os
import sys

import pytest

from cicada.ipod.device import write_guard as wg
from cicada.ipod.device.write_guard import (
    PHOTOS_DIRNAME,
    AmbiguousMountError,
    MountNotFoundError,
    PathOutsideIpodControlError,
    ProtectedPathError,
    ReadOnlyFilesystemError,
    WriteGuardError,
    WrongDeviceError,
    assert_deletable,
    assert_within_ipod_control,
    assert_writable,
    is_protected_path,
    resolve_mount,
    safe_rmtree,
)


@pytest.fixture
def ipod(tmp_path):
    """Árbol mínimo de un iPod: <mount>/iPod_Control/{iTunes,Device,Music/F04}."""
    mount = tmp_path / "IPOD"
    control = mount / "iPod_Control"
    (control / "iTunes" / "iTunes Library.itlp").mkdir(parents=True)
    (control / "Device").mkdir(parents=True)
    (control / "Music" / "F04").mkdir(parents=True)
    (control / "iTunes" / "iTunesCDB").write_bytes(b"cdb")
    return mount


# --------------------------------------------------------------------------- #
# resolve_mount
# --------------------------------------------------------------------------- #
def test_resolve_mount_encuentra_ipod(ipod):
    assert resolve_mount(candidates=[ipod]) == ipod.resolve()


def test_resolve_mount_desaparecido_lanza_excepcion_especifica(ipod):
    # Montado -> OK.
    assert resolve_mount(candidates=[ipod]) == ipod.resolve()
    # Se desmonta a mitad de uso: el directorio desaparece.
    import shutil
    shutil.rmtree(ipod)
    with pytest.raises(MountNotFoundError):
        resolve_mount(candidates=[ipod])


def test_resolve_mount_directorio_sin_ipod_control_no_cuenta(tmp_path):
    vacio = tmp_path / "USB"
    vacio.mkdir()
    with pytest.raises(MountNotFoundError):
        resolve_mount(candidates=[vacio])


def test_resolve_mount_no_cachea(ipod):
    # Dos llamadas revalidan de verdad: si desaparece entre medias, la 2ª falla.
    resolve_mount(candidates=[ipod])
    import shutil
    shutil.rmtree(ipod)
    with pytest.raises(MountNotFoundError):
        resolve_mount(candidates=[ipod])


def test_resolve_mount_varios_sin_guid_es_ambiguo(tmp_path):
    a = tmp_path / "IPOD1"
    b = tmp_path / "IPOD2"
    for m in (a, b):
        (m / "iPod_Control").mkdir(parents=True)
    with pytest.raises(AmbiguousMountError):
        resolve_mount(candidates=[a, b])


def test_resolve_mount_guid_coincide(ipod, tmp_path, monkeypatch):
    otro = tmp_path / "IPOD2"
    (otro / "iPod_Control").mkdir(parents=True)
    guids = {ipod.resolve(): "AAAA1111", otro.resolve(): "BBBB2222"}
    monkeypatch.setattr(wg, "_read_mount_guid", lambda m: guids.get(m.resolve()))
    assert resolve_mount("AAAA1111", candidates=[ipod, otro]) == ipod.resolve()


def test_resolve_mount_guid_no_coincide(ipod, monkeypatch):
    monkeypatch.setattr(wg, "_read_mount_guid", lambda m: "REALGUID")
    with pytest.raises(WrongDeviceError):
        resolve_mount("OTROGUID", candidates=[ipod])


# --------------------------------------------------------------------------- #
# assert_within_ipod_control
# --------------------------------------------------------------------------- #
def test_ruta_legitima_dentro_de_music_f04_aceptada(ipod):
    destino = ipod / "iPod_Control" / "Music" / "F04" / "ABCD.mp3"
    resuelta = assert_within_ipod_control(destino, ipod)
    assert resuelta == destino.resolve()


def test_ruta_fuera_de_ipod_control_rechazada(ipod, tmp_path):
    fuera = tmp_path / "otro_sitio" / "archivo.mp3"
    with pytest.raises(PathOutsideIpodControlError):
        assert_within_ipod_control(fuera, ipod)


def test_ruta_en_raiz_del_mount_fuera_de_control_rechazada(ipod):
    # <mount>/algo NO está en iPod_Control/ -> rechazado.
    with pytest.raises(PathOutsideIpodControlError):
        assert_within_ipod_control(ipod / "algo.txt", ipod)


def test_traversal_doble_puntopunto_rechazado(ipod):
    # iPod_Control/Music/../../.. sale del árbol; resolverlo lo delata.
    trampa = ipod / "iPod_Control" / "Music" / ".." / ".." / ".." / "etc"
    with pytest.raises(PathOutsideIpodControlError):
        assert_within_ipod_control(trampa, ipod)


def test_traversal_hasta_raiz_del_sistema_rechazado(ipod):
    trampa = ipod / "iPod_Control" / ".." / ".." / ".." / ".." / ".." / "etc" / "passwd"
    with pytest.raises(PathOutsideIpodControlError):
        assert_within_ipod_control(trampa, ipod)


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks POSIX")
def test_symlink_que_apunta_fuera_rechazado(ipod, tmp_path):
    secreto = tmp_path / "secreto"
    secreto.mkdir()
    (secreto / "passwd").write_bytes(b"x")
    # Symlink DENTRO de iPod_Control que escapa del árbol.
    enlace = ipod / "iPod_Control" / "escape"
    enlace.symlink_to(secreto)
    with pytest.raises(PathOutsideIpodControlError):
        assert_within_ipod_control(enlace / "passwd", ipod)


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks POSIX")
def test_symlink_interno_valido_aceptado(ipod):
    # Un symlink que apunta DENTRO del árbol sí se acepta.
    real = ipod / "iPod_Control" / "Music" / "F04"
    enlace = ipod / "iPod_Control" / "atajo"
    enlace.symlink_to(real)
    resuelta = assert_within_ipod_control(enlace / "x.mp3", ipod)
    assert resuelta == (real / "x.mp3").resolve()


# --------------------------------------------------------------------------- #
# Prohibición de borrado recursivo
# --------------------------------------------------------------------------- #
def test_borrado_recursivo_de_ipod_control_rechazado(ipod):
    control = ipod / "iPod_Control"
    with pytest.raises(ProtectedPathError):
        assert_deletable(control, ipod)
    with pytest.raises(ProtectedPathError):
        safe_rmtree(control, ipod)
    assert control.is_dir()  # sigue intacto


def test_borrado_recursivo_de_itunes_rechazado(ipod):
    itunes = ipod / "iPod_Control" / "iTunes"
    with pytest.raises(ProtectedPathError):
        assert_deletable(itunes, ipod)
    with pytest.raises(ProtectedPathError):
        safe_rmtree(itunes, ipod)
    assert itunes.is_dir()  # intacto


def test_borrado_de_itunes_via_traversal_tambien_rechazado(ipod):
    # iPod_Control/Music/../iTunes resuelve a iPod_Control/iTunes -> protegido.
    trampa = ipod / "iPod_Control" / "Music" / ".." / "iTunes"
    with pytest.raises(ProtectedPathError):
        safe_rmtree(trampa, ipod)
    assert (ipod / "iPod_Control" / "iTunes").is_dir()


def test_borrado_recursivo_del_mount_rechazado_por_estar_fuera(ipod):
    # rmtree del mount entero: fuera de iPod_Control -> rechazado (no protegido,
    # sino fuera del árbol permitido).
    with pytest.raises(PathOutsideIpodControlError):
        safe_rmtree(ipod, ipod)
    assert ipod.is_dir()


def test_borrado_recursivo_de_subdir_permitido(ipod):
    # Un subdirectorio NO protegido dentro de iTunes sí se puede borrar.
    victima = ipod / "iPod_Control" / "iTunes" / "iTunes Library.itlp"
    assert victima.is_dir()
    safe_rmtree(victima, ipod)
    assert not victima.exists()
    assert (ipod / "iPod_Control" / "iTunes").is_dir()  # el padre protegido intacto


def test_is_protected_path(ipod):
    assert is_protected_path(ipod / "iPod_Control", ipod) is True
    assert is_protected_path(ipod / "iPod_Control" / "iTunes", ipod) is True
    assert is_protected_path(ipod / "iPod_Control" / "Music" / "F04", ipod) is False


# --------------------------------------------------------------------------- #
# assert_writable
# --------------------------------------------------------------------------- #
def test_writable_ok(ipod):
    assert_writable(ipod)  # tmp_path es escribible -> no lanza


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="chmod de solo lectura no aplica como root ni en Windows",
)
def test_writable_solo_lectura_rechazado(ipod):
    control = ipod / "iPod_Control"
    original = control.stat().st_mode
    os.chmod(control, 0o500)  # r-x: sin permiso de escritura
    try:
        with pytest.raises(ReadOnlyFilesystemError):
            assert_writable(ipod)
    finally:
        os.chmod(control, original)


# --------------------------------------------------------------------------- #
# Jerarquía de excepciones
# --------------------------------------------------------------------------- #
def test_todas_las_excepciones_derivan_de_writeguarderror():
    for exc in (MountNotFoundError, AmbiguousMountError, WrongDeviceError,
                PathOutsideIpodControlError, ReadOnlyFilesystemError,
                ProtectedPathError):
        assert issubclass(exc, WriteGuardError)


def test_se_puede_distinguir_desmontaje_de_ruta_invalida(ipod, tmp_path):
    # Quien captura debe poder separar los dos casos.
    import shutil
    shutil.rmtree(ipod)
    with pytest.raises(MountNotFoundError):
        resolve_mount(candidates=[ipod])
    # ...vs ruta inválida es otra rama del árbol de excepciones.
    assert not issubclass(PathOutsideIpodControlError, MountNotFoundError)
    assert not issubclass(MountNotFoundError, PathOutsideIpodControlError)


# --------------------------------------------------------------------------- #
# root= (Etapa 6h) — Photos/ vive a nivel de volumen, fuera de iPod_Control/
# --------------------------------------------------------------------------- #
def test_root_default_sigue_siendo_ipod_control(ipod):
    """Sin root=, el comportamiento es idéntico al de antes de 6h (nada
    regresó para el resto del proyecto, que nunca pasa root=)."""
    target = ipod / "iPod_Control" / "iTunes" / "iTunesCDB"
    assert assert_within_ipod_control(target, ipod) == target.resolve()
    outside = ipod / "Photos" / "Photo Database"
    with pytest.raises(PathOutsideIpodControlError):
        assert_within_ipod_control(outside, ipod)


def test_root_arbitrario_no_conocido_es_rechazado(ipod):
    """root= NO es un confinador genérico a cualquier subdirectorio — está
    cerrado a las dos raíces conocidas. Un tercer valor debe fallar ANTES
    de tocar el filesystem, sin importar si esa ruta existe o es válida
    en sí misma."""
    (ipod / "Music").mkdir()
    target = ipod / "Music" / "song.mp3"
    with pytest.raises(ValueError, match="no es una raíz segura conocida"):
        assert_within_ipod_control(target, ipod, root="Music")
    with pytest.raises(ValueError):
        assert_within_ipod_control(target, ipod, root="../../etc")
    with pytest.raises(ValueError):
        assert_within_ipod_control(target, ipod, root="")


def test_root_photos_permite_photos_fuera_de_ipod_control(ipod):
    (ipod / "Photos" / "Thumbs").mkdir(parents=True)
    target = ipod / "Photos" / "Photo Database"
    assert assert_within_ipod_control(target, ipod, root=PHOTOS_DIRNAME) == target.resolve()


def test_root_photos_rechaza_ipod_control(ipod):
    """root=Photos no es un bypass general — sigue confinando a ESA raíz."""
    target = ipod / "iPod_Control" / "iTunes" / "iTunesCDB"
    with pytest.raises(PathOutsideIpodControlError):
        assert_within_ipod_control(target, ipod, root=PHOTOS_DIRNAME)


def test_root_photos_rechaza_traversal_fuera_del_volumen(ipod):
    outside = ipod / "Photos" / ".." / ".." / "etc" / "passwd"
    with pytest.raises(PathOutsideIpodControlError):
        assert_within_ipod_control(outside, ipod, root=PHOTOS_DIRNAME)


def test_photos_root_esta_protegida_de_borrado_recursivo_completo(ipod):
    (ipod / "Photos").mkdir()
    assert is_protected_path(ipod / "Photos", ipod)
    with pytest.raises(ProtectedPathError):
        assert_deletable(ipod / "Photos", ipod, root=PHOTOS_DIRNAME)


def test_safe_rmtree_con_root_photos_borra_subdirectorio_no_protegido(ipod):
    stale = ipod / "Photos" / "Thumbs" / "stale_dir"
    stale.mkdir(parents=True)
    (stale / "leftover.bin").write_bytes(b"x")
    safe_rmtree(stale, ipod, root=PHOTOS_DIRNAME)
    assert not stale.exists()


# --------------------------------------------------------------------------- #
# Sanity check de mutación (aplicado manualmente sobre write_guard.py,
# resultado registrado en docs/VENDORED.md Paquete 9 Etapa 6h)
# --------------------------------------------------------------------------- #
