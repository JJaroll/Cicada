"""Tests de cicada/ipod/device/backup — backup/restore vía write_guard.

Todo con tmp_path; ningún dispositivo real. Incluye round-trip.
"""
import os
import tarfile

import pytest
import zstandard

from cicada.ipod.device import backup as bk
from cicada.ipod.device.backup import (
    BackupIntegrityError,
    BackupMode,
    UNKNOWN_GUID,
    create_backup,
    list_backups,
    restore_backup,
)
from cicada.ipod.device.write_guard import PathOutsideIpodControlError


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def ipod(tmp_path):
    """Árbol de iPod con datos en iTunes/, Device/ y Music/F04, más ruido macOS."""
    mount = tmp_path / "IPOD"
    control = mount / "iPod_Control"
    itunes = control / "iTunes" / "iTunes Library.itlp"
    device = control / "Device"
    music = control / "Music" / "F04"
    for d in (itunes, device, music):
        d.mkdir(parents=True)

    (control / "iTunes" / "iTunesCDB").write_bytes(b"CDB-original")
    (itunes / "Library.itdb").write_bytes(b"itdb-original")
    (device / "SysInfoExtended").write_bytes(b"sysinfo")
    (music / "SONG.MP3").write_bytes(b"audio-bytes")

    # Ruido macOS/FAT32 que NO debe ir al backup.
    (control / "iTunes" / "._iTunesCDB").write_bytes(b"junk-fork")
    (control / ".DS_Store").write_bytes(b"junk")
    (control / ".Trashes").mkdir()
    (control / ".Trashes" / "borrame").write_bytes(b"junk")
    return mount


@pytest.fixture
def backups_dir(tmp_path):
    return tmp_path / "backups"


def _snapshot(root):
    """{ruta_relativa: bytes} de los archivos reales bajo root (sin artefactos macOS)."""
    from cicada.ipod.util import fsfilter
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not fsfilter.is_macos_artifact(d)]
        for fn in fns:
            if fsfilter.is_macos_artifact(fn):
                continue
            p = os.path.join(dp, fn)
            out[os.path.relpath(p, root)] = open(p, "rb").read()
    return out


# --------------------------------------------------------------------------- #
# create_backup
# --------------------------------------------------------------------------- #
def test_backup_db_only_por_defecto(ipod, backups_dir):
    archive = create_backup(ipod, candidates=[ipod], backups_dir=backups_dir)
    assert archive.exists()
    # Nombre: <guid>_<timestamp>_<modo>.tar.zst con fallback de GUID.
    assert archive.name.startswith(f"{UNKNOWN_GUID}_")
    assert archive.name.endswith("_db-only.tar.zst")
    # Ubicación: <backups_dir>/<guid>/
    assert archive.parent == backups_dir / UNKNOWN_GUID


def test_backup_db_only_no_incluye_music(ipod, backups_dir):
    archive = create_backup(ipod, BackupMode.DB_ONLY, candidates=[ipod], backups_dir=backups_dir)
    names = set(bk._list_member_names(archive))
    assert any("iPod_Control/iTunes/iTunesCDB" == n for n in names)
    assert any("iPod_Control/Device/SysInfoExtended" == n for n in names)
    assert not any("Music" in n for n in names)  # Music/ excluido en db-only


def test_backup_full_incluye_music(ipod, backups_dir):
    archive = create_backup(ipod, BackupMode.FULL, candidates=[ipod], backups_dir=backups_dir)
    names = set(bk._list_member_names(archive))
    assert any(n.endswith("Music/F04/SONG.MP3") for n in names)
    assert archive.name.endswith("_full.tar.zst")


def test_backup_excluye_artefactos_macos(ipod, backups_dir):
    archive = create_backup(ipod, BackupMode.FULL, candidates=[ipod], backups_dir=backups_dir)
    names = bk._list_member_names(archive)
    assert not any("._iTunesCDB" in n for n in names)
    assert not any(".DS_Store" in n for n in names)
    assert not any(".Trashes" in n for n in names)  # ni el dir ni su contenido


def test_backup_verifica_integridad(ipod, backups_dir):
    # Camino feliz: no lanza.
    archive = create_backup(ipod, candidates=[ipod], backups_dir=backups_dir)
    # El contenido del tar coincide con el origen (misma verificación interna).
    seen = bk._read_archive_manifest(archive)
    assert seen["iPod_Control/iTunes/iTunesCDB"][1] == __import__("hashlib").sha256(b"CDB-original").hexdigest()


def test_backup_integridad_falla_borra_archivo(ipod, backups_dir, monkeypatch):
    # Forzamos un manifiesto que no casa con lo que se escribió -> integridad falla.
    real = bk._build_manifest
    def manifiesto_mentiroso(mount, mode):
        m = real(mount, mode)
        m["iPod_Control/iTunes/iTunesCDB"] = (999, "deadbeef")
        return m
    monkeypatch.setattr(bk, "_build_manifest", manifiesto_mentiroso)
    with pytest.raises(BackupIntegrityError):
        create_backup(ipod, candidates=[ipod], backups_dir=backups_dir)
    # No quedó ningún .tar.zst corrupto (ni .part).
    guid_dir = backups_dir / UNKNOWN_GUID
    assert list(guid_dir.glob("*.tar.zst")) == []
    assert list(guid_dir.glob("*.part")) == []


# --------------------------------------------------------------------------- #
# Rotación
# --------------------------------------------------------------------------- #
def test_rotacion_conserva_ultimos_20_db_only(ipod, backups_dir):
    from datetime import datetime, timezone, timedelta
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(25):
        create_backup(ipod, BackupMode.DB_ONLY, candidates=[ipod],
                      backups_dir=backups_dir, timestamp=base + timedelta(minutes=i))
    guid_dir = backups_dir / UNKNOWN_GUID
    restantes = sorted(guid_dir.glob("*_db-only.tar.zst"))
    assert len(restantes) == 20
    # Se conservan los MÁS RECIENTES (minutos 05..24).
    assert restantes[0].name.endswith("20260101T000500Z_db-only.tar.zst")
    assert restantes[-1].name.endswith("20260101T002400Z_db-only.tar.zst")


def test_rotacion_no_afecta_full(ipod, backups_dir):
    from datetime import datetime, timezone, timedelta
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(3):
        create_backup(ipod, BackupMode.FULL, candidates=[ipod],
                      backups_dir=backups_dir, timestamp=base + timedelta(minutes=i))
    for i in range(22):
        create_backup(ipod, BackupMode.DB_ONLY, candidates=[ipod],
                      backups_dir=backups_dir, timestamp=base + timedelta(hours=1, minutes=i))
    guid_dir = backups_dir / UNKNOWN_GUID
    assert len(list(guid_dir.glob("*_full.tar.zst"))) == 3       # full intactos
    assert len(list(guid_dir.glob("*_db-only.tar.zst"))) == 20   # db-only rotados


# --------------------------------------------------------------------------- #
# list_backups
# --------------------------------------------------------------------------- #
def test_list_backups_ordena_reciente_primero(ipod, backups_dir):
    from datetime import datetime, timezone, timedelta
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    create_backup(ipod, candidates=[ipod], backups_dir=backups_dir, timestamp=base)
    create_backup(ipod, BackupMode.FULL, candidates=[ipod], backups_dir=backups_dir,
                  timestamp=base + timedelta(days=1))
    infos = list_backups(backups_dir=backups_dir)
    assert len(infos) == 2
    assert infos[0].timestamp > infos[1].timestamp   # más reciente primero
    assert infos[0].mode is BackupMode.FULL
    assert infos[0].guid == UNKNOWN_GUID


def test_list_backups_vacio(backups_dir):
    assert list_backups(backups_dir=backups_dir) == []


# --------------------------------------------------------------------------- #
# restore: seguridad
# --------------------------------------------------------------------------- #
def test_restore_valida_destino_antes_de_escribir(ipod, backups_dir, tmp_path):
    # Un archivo malicioso con un miembro que escapa de iPod_Control debe
    # rechazarse SIN escribir nada.
    guid_dir = backups_dir / UNKNOWN_GUID
    guid_dir.mkdir(parents=True)
    evil = guid_dir / f"{UNKNOWN_GUID}_20260101T000000Z_full.tar.zst"
    cctx = zstandard.ZstdCompressor()
    with open(evil, "wb") as fh, cctx.stream_writer(fh) as zf:
        with tarfile.open(mode="w|", fileobj=zf) as tar:
            ti = tarfile.TarInfo("iPod_Control/../../escape.txt")
            data = b"pwned"
            ti.size = len(data)
            import io
            tar.addfile(ti, io.BytesIO(data))

    with pytest.raises(PathOutsideIpodControlError):
        restore_backup(evil, ipod, candidates=[ipod])
    # Nada escrito fuera del árbol.
    assert not (tmp_path / "escape.txt").exists()
    assert not (ipod.parent / "escape.txt").exists()


def test_restore_mount_desaparecido(ipod, backups_dir):
    archive = create_backup(ipod, candidates=[ipod], backups_dir=backups_dir)
    import shutil
    from cicada.ipod.device.write_guard import MountNotFoundError
    shutil.rmtree(ipod)
    with pytest.raises(MountNotFoundError):
        restore_backup(archive, ipod, candidates=[ipod])


# --------------------------------------------------------------------------- #
# ROUND-TRIP
# --------------------------------------------------------------------------- #
def test_round_trip_db_only(ipod, backups_dir):
    control = ipod / "iPod_Control"
    original = _snapshot(control / "iTunes")
    original_device = _snapshot(control / "Device")

    archive = create_backup(ipod, BackupMode.DB_ONLY, candidates=[ipod], backups_dir=backups_dir)

    # Modificar el árbol de las formas que un usuario podría: editar, borrar, añadir.
    (control / "iTunes" / "iTunesCDB").write_bytes(b"CDB-CORROMPIDO")          # editado
    (control / "iTunes" / "iTunes Library.itlp" / "Library.itdb").unlink()     # borrado
    (control / "iTunes" / "playlist-fantasma.itdb").write_bytes(b"basura")     # añadido
    (control / "Device" / "SysInfoExtended").write_bytes(b"tocado")

    restore_backup(archive, ipod, candidates=[ipod])

    # Vuelve EXACTAMENTE al estado original.
    assert _snapshot(control / "iTunes") == original
    assert _snapshot(control / "Device") == original_device
    # El archivo añadido tras el backup fue podado.
    assert not (control / "iTunes" / "playlist-fantasma.itdb").exists()


def test_round_trip_db_only_no_toca_music(ipod, backups_dir):
    control = ipod / "iPod_Control"
    archive = create_backup(ipod, BackupMode.DB_ONLY, candidates=[ipod], backups_dir=backups_dir)
    # Cambiamos Music/ (fuera del alcance db-only): restore NO debe tocarlo.
    (control / "Music" / "F04" / "SONG.MP3").write_bytes(b"cancion-nueva")
    restore_backup(archive, ipod, candidates=[ipod])
    assert (control / "Music" / "F04" / "SONG.MP3").read_bytes() == b"cancion-nueva"


def test_round_trip_full(ipod, backups_dir):
    control = ipod / "iPod_Control"
    original = _snapshot(control)

    archive = create_backup(ipod, BackupMode.FULL, candidates=[ipod], backups_dir=backups_dir)

    (control / "Music" / "F04" / "SONG.MP3").write_bytes(b"editada")
    (control / "Music" / "F05").mkdir()
    (control / "Music" / "F05" / "EXTRA.MP3").write_bytes(b"nueva")
    (control / "iTunes" / "iTunesCDB").write_bytes(b"cambiado")

    restore_backup(archive, ipod, candidates=[ipod])

    assert _snapshot(control) == original
    assert not (control / "Music" / "F05").exists()  # dir extra podado


def test_round_trip_protege_ipod_control(ipod, backups_dir, monkeypatch):
    # Garantía dura: durante el restore NUNCA se llama a shutil.rmtree sobre
    # iPod_Control ni iTunes (solo safe_rmtree, que los rechazaría).
    control = (ipod / "iPod_Control").resolve()
    itunes = (control / "iTunes").resolve()
    import shutil
    real_rmtree = shutil.rmtree
    def guarded_rmtree(path, *a, **k):
        assert os.path.realpath(path) not in (str(control), str(itunes)), \
            f"restore intentó rmtree de un directorio protegido: {path}"
        return real_rmtree(path, *a, **k)
    monkeypatch.setattr(shutil, "rmtree", guarded_rmtree)

    archive = create_backup(ipod, BackupMode.FULL, candidates=[ipod], backups_dir=backups_dir)
    (control / "iTunes" / "iTunesCDB").write_bytes(b"x")
    restore_backup(archive, ipod, candidates=[ipod])
    assert itunes.is_dir() and control.is_dir()
