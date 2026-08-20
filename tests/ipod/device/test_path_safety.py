"""Tests de path_safety (Etapa 6e — infra para Fotos, vendorizado de iOpenPod).

Sin dispositivo real: contención de rutas es lógica pura de filesystem, se
verifica con tmp_path simulando el árbol del iPod.
"""
import sys

import pytest

from cicada.ipod.device.path_safety import UnsafeDevicePathError, resolve_device_path


def test_resuelve_ruta_normal_dentro_del_subarbol(tmp_path):
    (tmp_path / "Photos" / "Thumbs").mkdir(parents=True)
    resolved = resolve_device_path(tmp_path, "Photos/Thumbs/F1005_1.ithmb", allowed_subtree="Photos")
    assert resolved == (tmp_path / "Photos" / "Thumbs" / "F1005_1.ithmb").resolve()


def test_rechaza_parent_traversal():
    with pytest.raises(UnsafeDevicePathError):
        resolve_device_path("/tmp/ipod", "Photos/../../etc/passwd", allowed_subtree="Photos")


def test_rechaza_ruta_absoluta():
    with pytest.raises(UnsafeDevicePathError):
        resolve_device_path("/tmp/ipod", "/etc/passwd", allowed_subtree="Photos")


def test_rechaza_ruta_fuera_del_subarbol_permitido():
    with pytest.raises(UnsafeDevicePathError):
        resolve_device_path("/tmp/ipod", "iPod_Control/iTunes/iTunesCDB", allowed_subtree="Photos")


def test_rechaza_nul_byte():
    with pytest.raises(UnsafeDevicePathError):
        resolve_device_path("/tmp/ipod", "Photos/foo\x00bar.jpg", allowed_subtree="Photos")


def test_rechaza_componente_vacio():
    with pytest.raises(UnsafeDevicePathError):
        resolve_device_path("/tmp/ipod", "Photos//foo.jpg", allowed_subtree="Photos")


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks no POSIX")
def test_rechaza_symlink_que_escapa_del_subarbol(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("no debería ser accesible")
    photos = tmp_path / "Photos"
    photos.mkdir()
    (photos / "escape").symlink_to(outside)
    with pytest.raises(UnsafeDevicePathError):
        resolve_device_path(tmp_path, "Photos/escape/secret.txt", allowed_subtree="Photos")


def test_permite_subdirectorios_profundos_dentro_del_subarbol(tmp_path):
    deep = tmp_path / "Photos" / "Full Resolution" / "iOpenPod"
    deep.mkdir(parents=True)
    resolved = resolve_device_path(
        tmp_path, "Photos/Full Resolution/iOpenPod/foto_00123.jpg", allowed_subtree="Photos",
    )
    assert resolved == (deep / "foto_00123.jpg").resolve()


# --------------------------------------------------------------------------- #
# Sanity check de mutación: confirmar que el chequeo explícito de symlinks
# detecta el bug real, no solo la defensa en profundidad de resolve()
# después. resolve_device_path tiene DOS capas contra symlinks: el walk
# explícito de _reject_link_or_reparse_components y el chequeo final basado
# en Path.resolve() — deshabilitar solo la primera no basta para que el test
# de arriba deje de fallar (la segunda capa igual lo atrapa), así que la
# mutación se prueba contra _reject_link_or_reparse_components() en
# aislamiento, no a través del wrapper completo.
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(sys.platform == "win32", reason="symlinks no POSIX")
def test_reject_link_detecta_symlink_en_aislamiento(tmp_path):
    from cicada.ipod.device.path_safety import _reject_link_or_reparse_components

    photos = tmp_path / "Photos"
    photos.mkdir()
    (photos / "real_dir").mkdir()
    (photos / "escape").symlink_to(photos / "real_dir")

    with pytest.raises(UnsafeDevicePathError):
        _reject_link_or_reparse_components(tmp_path, ("Photos", "escape", "foo.jpg"))


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks no POSIX")
def test_mutacion_sin_s_islnk_el_symlink_no_se_detecta(tmp_path, monkeypatch):
    """Sanity check: si se rompe el chequeo S_ISLNK dentro de
    _reject_link_or_reparse_components, deja de detectar el symlink —
    confirma que el test anterior ejerce esa línea específica."""
    import cicada.ipod.device.path_safety as mod

    photos = tmp_path / "Photos"
    photos.mkdir()
    (photos / "real_dir").mkdir()
    (photos / "escape").symlink_to(photos / "real_dir")

    monkeypatch.setattr(mod.stat, "S_ISLNK", lambda mode: False)
    # Sin S_ISLNK funcionando, el symlink ya no se detecta (reparse_flag
    # tampoco aplica en POSIX) — no debería lanzar.
    mod._reject_link_or_reparse_components(tmp_path, ("Photos", "escape", "foo.jpg"))
