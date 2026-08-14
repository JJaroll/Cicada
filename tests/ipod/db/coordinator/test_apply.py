"""Tests unitarios para el orquestador transaccional apply (apply.py) — Etapa 2c."""
from __future__ import annotations

import os
import plistlib
import sqlite3
from pathlib import Path

import pytest

wasmtime = pytest.importorskip("wasmtime", reason="wasmtime no instalado")

from cicada.ipod.db.coordinator.apply import (
    ApplyResult,
    PostCommitVerifyError,
    StalePlanError,
    apply,
    get_inflight_marker,
    recover_inflight_commit,
    set_inflight_marker,
)
from cicada.ipod.db.coordinator.consent import (
    ConsentRequiredError,
    get_consent_record,
    has_music_app_consent,
    record_music_app_consent,
)
from cicada.ipod.db.coordinator.plan import (
    DATABASE_TARGET_RELPATHS,
    Plan,
    PreStateFingerprint,
    create_plan,
)
from cicada.ipod.db.parser import load_ipod_library
from cicada.ipod.db.writer.mhit_writer import TrackInfo
from cicada.ipod.db.writer.verify import verify_hashab
from cicada.ipod.device.capabilities import capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.device_info import DeviceInfo

GUID_STR = "000A27002484DDFB"
GUID_BYTES = bytes.fromhex(GUID_STR)


def _setup_mock_ipod_environment(mount: Path) -> DeviceInfo:
    """Crea una estructura completa de iPod con SysInfoExtended y bases iniciales."""
    device_dir = mount / "iPod_Control" / "Device"
    device_dir.mkdir(parents=True, exist_ok=True)
    sie_data = plistlib.dumps({
        "FireWireGUID": GUID_STR,
        "FamilyID": 18,
        "SerialNumber": "C17X1234F19R",
        "ModelNumStr": "MD481",
    })
    (device_dir / "SysInfoExtended").write_bytes(sie_data)

    itunes_dir = mount / "iPod_Control" / "iTunes"
    itlp_dir = itunes_dir / "iTunes Library.itlp"
    itlp_dir.mkdir(parents=True, exist_ok=True)

    caps = capabilities_for_family_gen("iPod Nano", "7th Gen")
    dev = DeviceInfo(
        mount=mount,
        firewire_guid=GUID_STR,
        family="iPod Nano",
        generation="7th Gen",
        family_id=18,
        checksum=ChecksumType.HASHAB,
        guid_provenance="disk",
        capabilities=caps,
    )

    # Base inicial dummy con 1 track
    initial_tracks = [
        TrackInfo(
            title="Initial Song",
            artist="Initial Artist",
            album="Initial Album",
            location=":iPod_Control:Music:F00:INIT.mp3",
            db_track_id=500,
        )
    ]
    init_plan = create_plan(mount, initial_tracks, device_info=dev)

    # Instalar manualmente la base inicial
    (itunes_dir / "iTunesCDB").write_bytes((init_plan.staging_dir / "iTunesCDB").read_bytes())
    for fn in ("Library.itdb", "Locations.itdb", "Locations.itdb.cbk", "Dynamic.itdb", "Extras.itdb", "Genius.itdb"):
        (itlp_dir / fn).write_bytes((init_plan.staging_dir / "iTunes Library.itlp" / fn).read_bytes())

    return dev


def _new_tracks() -> list[TrackInfo]:
    return [
        TrackInfo(
            title="New Song 1",
            artist="New Artist 1",
            album="New Album 1",
            location=":iPod_Control:Music:F00:NEW1.mp3",
            db_track_id=1001,
        ),
        TrackInfo(
            title="New Song 2",
            artist="New Artist 2",
            album="New Album 2",
            location=":iPod_Control:Music:F01:NEW2.mp3",
            db_track_id=1002,
        ),
    ]


def test_apply_success_end_to_end(tmp_path: Path):
    """Ejecuta un ciclo completo exitoso de apply con verificación post-commit."""
    mount = tmp_path / "ipod_mount"
    dev = _setup_mock_ipod_environment(mount)
    consent_dir = tmp_path / "consent"
    backups_dir = tmp_path / "backups"
    commit_dir = tmp_path / "commit"

    plan = create_plan(
        mount,
        _new_tracks(),
        device_info=dev,
        consent_dir=consent_dir,
    )

    progress_log = []

    def on_progress(msg: str, frac: float):
        progress_log.append((msg, frac))

    res = apply(
        plan,
        mount=mount,
        device_info=dev,
        consent_ack=True,
        consent_dir=consent_dir,
        backups_dir=backups_dir,
        commit_dir=commit_dir,
        on_progress=on_progress,
    )

    assert res.success is True
    assert res.restored_from_backup is False
    assert res.tracks_written == 2
    assert res.first_write_committed is True
    assert res.backup_path is not None
    assert res.backup_path.is_file()

    # Progreso invocado
    assert len(progress_log) >= 5
    assert progress_log[-1][1] == 1.0

    # Inflight marker limpio
    assert get_inflight_marker(GUID_STR, commit_dir=commit_dir) is None

    # Consentimiento actualizado
    rec = get_consent_record(GUID_STR, consent_dir=consent_dir)
    assert rec is not None
    assert rec.first_write_committed_at is not None

    # Post-estado verificado directamente en el iPod
    itunes_dir = mount / "iPod_Control" / "iTunes"
    cdb_data = (itunes_dir / "iTunesCDB").read_bytes()
    assert verify_hashab(cdb_data, GUID_BYTES)

    lib = load_ipod_library(str(itunes_dir / "iTunesCDB"), mount=str(mount))
    assert lib is not None
    assert len(lib["mhlt"]) == 2

    # Sin residuos de temporales .cicada-new
    for root, _dirs, files in os.walk(itunes_dir):
        for f in files:
            assert not f.endswith(".cicada-new")


def test_apply_consent_required_aborts(tmp_path: Path):
    """Si se requiere consentimiento y consent_ack=False, apply se detiene y no muta."""
    mount = tmp_path / "ipod_mount"
    dev = _setup_mock_ipod_environment(mount)
    consent_dir = tmp_path / "consent"

    plan = create_plan(mount, _new_tracks(), device_info=dev, consent_dir=consent_dir)
    assert plan.consent_needed is True

    fp_before = PreStateFingerprint.capture(mount)

    with pytest.raises(ConsentRequiredError):
        apply(
            plan,
            mount=mount,
            device_info=dev,
            consent_ack=False,
            consent_dir=consent_dir,
        )

    # Dispositivo 100% intacto
    assert fp_before.matches(mount)


def test_apply_stale_plan_aborts(tmp_path: Path):
    """Si el estado en disco cambia después de crear el plan, apply se aborta."""
    mount = tmp_path / "ipod_mount"
    dev = _setup_mock_ipod_environment(mount)
    consent_dir = tmp_path / "consent"

    plan = create_plan(mount, _new_tracks(), device_info=dev, consent_dir=consent_dir)

    # Simular cambio en el iPod antes de apply
    cdb_file = mount / "iPod_Control" / "iTunes" / "iTunesCDB"
    cdb_file.write_bytes(b"altered by external app")

    with pytest.raises(StalePlanError):
        apply(
            plan,
            mount=mount,
            device_info=dev,
            consent_ack=True,
            consent_dir=consent_dir,
        )


def test_apply_commit_failure_triggers_rollback_byte_exact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Fallo en Fase D (Commit) dispara rollback inmediato dejando el estado byte-idéntico."""
    mount = tmp_path / "ipod_mount"
    dev = _setup_mock_ipod_environment(mount)
    consent_dir = tmp_path / "consent"
    backups_dir = tmp_path / "backups"
    commit_dir = tmp_path / "commit"

    plan = create_plan(mount, _new_tracks(), device_info=dev, consent_dir=consent_dir)
    fp_before = PreStateFingerprint.capture(mount)

    real_replace = os.replace

    def mock_replace(src, dst):
        if "Library.itdb" in str(dst) and not str(dst).endswith(".cicada-new"):
            raise OSError("Simulated I/O crash during atomic rename")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", mock_replace)

    res = apply(
        plan,
        mount=mount,
        device_info=dev,
        consent_ack=True,
        consent_dir=consent_dir,
        backups_dir=backups_dir,
        commit_dir=commit_dir,
    )

    assert res.success is False
    assert res.restored_from_backup is True
    assert "Fallo en commit" in (res.error or "")

    # Inflight marker limpio
    assert get_inflight_marker(GUID_STR, commit_dir=commit_dir) is None

    # Estado previo restaurado byte-exacto
    assert fp_before.matches(mount)


def test_apply_post_commit_verify_failure_triggers_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Fallo en Fase E (Verify) dispara rollback inmediato dejando el estado previo intacto."""
    mount = tmp_path / "ipod_mount"
    dev = _setup_mock_ipod_environment(mount)
    consent_dir = tmp_path / "consent"
    backups_dir = tmp_path / "backups"
    commit_dir = tmp_path / "commit"

    plan = create_plan(mount, _new_tracks(), device_info=dev, consent_dir=consent_dir)
    fp_before = PreStateFingerprint.capture(mount)

    def mock_load_ipod_library(path, merge_playcounts=True, mount=None):
        return {"mhlt": []}  # 0 tracks en vez de 2

    import sys
    apply_module = sys.modules["cicada.ipod.db.coordinator.apply"]
    monkeypatch.setattr(apply_module, "load_ipod_library", mock_load_ipod_library)

    res = apply(
        plan,
        mount=mount,
        device_info=dev,
        consent_ack=True,
        consent_dir=consent_dir,
        backups_dir=backups_dir,
        commit_dir=commit_dir,
    )

    assert res.success is False
    assert res.restored_from_backup is True
    assert "Verificación post-commit fallida" in (res.error or "")

    # Estado previo restaurado
    assert fp_before.matches(mount)


def test_recover_inflight_commit_on_startup(tmp_path: Path):
    """Recuperación cross-sesión de un commit que quedó interrumpido."""
    mount = tmp_path / "ipod_mount"
    dev = _setup_mock_ipod_environment(mount)
    backups_dir = tmp_path / "backups"
    commit_dir = tmp_path / "commit"

    fp_before = PreStateFingerprint.capture(mount)

    # Crear un backup válido
    from cicada.ipod.device.backup import BackupMode, create_backup
    bkp = create_backup(mount, mode=BackupMode.DB_ONLY, guid=GUID_STR, backups_dir=backups_dir)

    # Simular que el disco quedó a medio mutar y con un archivo .cicada-new
    itunes_dir = mount / "iPod_Control" / "iTunes"
    (itunes_dir / "iTunesCDB").write_bytes(b"corrupted half-written data")
    (itunes_dir / "orphan.cicada-new").write_bytes(b"leftover temp")

    # Registrar el marcador inflight
    set_inflight_marker(GUID_STR, bkp, mount, commit_dir=commit_dir)
    assert get_inflight_marker(GUID_STR, commit_dir=commit_dir) is not None

    # Ejecutar recuperación
    ok = recover_inflight_commit(mount, GUID_STR, commit_dir=commit_dir)
    assert ok is True

    # Marcador eliminado
    assert get_inflight_marker(GUID_STR, commit_dir=commit_dir) is None

    # Temporal purgado y estado previo restaurado byte-exacto
    assert not (itunes_dir / "orphan.cicada-new").exists()
    assert fp_before.matches(mount)
