"""Tests para la CLI del módulo iPod (cicada/ipod/cli.py)."""
from __future__ import annotations

import json
import plistlib
from pathlib import Path

import pytest

wasmtime = pytest.importorskip("wasmtime", reason="wasmtime no instalado")

from cicada.ipod.cli import main
from cicada.ipod.db.coordinator.plan import create_plan
from cicada.ipod.db.writer.mhit_writer import TrackInfo
from cicada.ipod.device.capabilities import capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.device_info import DeviceInfo

GUID_STR = "000A27002484DDFB"


@pytest.fixture
def mock_cli_ipod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    mount = tmp_path / "ipod_mount"
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

    init_tracks = [
        TrackInfo(
            title="Initial CLI Song",
            artist="CLI Artist",
            album="CLI Album",
            location=":iPod_Control:Music:F00:INIT.mp3",
            db_track_id=100,
        )
    ]
    init_plan = create_plan(mount, init_tracks, device_info=dev)

    (itunes_dir / "iTunesCDB").write_bytes((init_plan.staging_dir / "iTunesCDB").read_bytes())
    for fn in ("Library.itdb", "Locations.itdb", "Locations.itdb.cbk", "Dynamic.itdb", "Extras.itdb", "Genius.itdb"):
        (itlp_dir / fn).write_bytes((init_plan.staging_dir / "iTunes Library.itlp" / fn).read_bytes())

    monkeypatch.setattr("cicada.ipod.device.write_guard._candidate_mounts", lambda: [mount])
    monkeypatch.setenv("CICADA_HOME", str(tmp_path / "cicada_home"))

    return mount


def _write_sample_tracks_file(path: Path) -> Path:
    tracks = [
        {
            "Title": "CLI Track 1",
            "Artist": "Artist 1",
            "Album": "Album 1",
            "Location": ":iPod_Control:Music:F00:C1.mp3",
            "db_track_id": 301,
        },
        {
            "Title": "CLI Track 2",
            "Artist": "Artist 2",
            "Album": "Album 2",
            "Location": ":iPod_Control:Music:F01:C2.mp3",
            "db_track_id": 302,
        },
    ]
    path.write_text(json.dumps(tracks), encoding="utf-8")
    return path


def test_cli_status(mock_cli_ipod: Path, capsys: pytest.CaptureFixture):
    code = main(["status"])
    assert code == 0
    captured = capsys.readouterr()
    assert "iPod Nano" in captured.out
    assert GUID_STR in captured.out
    assert "[write-safe]" in captured.out


def test_cli_tracks(mock_cli_ipod: Path, capsys: pytest.CaptureFixture):
    code = main(["tracks"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Initial CLI Song" in captured.out


def test_cli_plan(mock_cli_ipod: Path, tmp_path: Path, capsys: pytest.CaptureFixture):
    tracks_file = _write_sample_tracks_file(tmp_path / "tracks.json")
    code = main(["plan", "--tracks-file", str(tracks_file)])
    assert code == 0
    captured = capsys.readouterr()
    assert "RESUMEN DEL PLAN" in captured.out
    assert "Total pistas  : 2" in captured.out
    assert "iTunesCDB" in captured.out


def test_cli_sync_flow(mock_cli_ipod: Path, tmp_path: Path, capsys: pytest.CaptureFixture):
    tracks_file = _write_sample_tracks_file(tmp_path / "tracks.json")

    # 1. Sync sin ack de consentimiento falla con código != 0
    code_fail = main(["sync", "--tracks-file", str(tracks_file)])
    assert code_fail != 0
    err = capsys.readouterr().err
    assert "ADVERTENCIA" in err

    # 2. Sync con --ack-consent tiene éxito
    code_ok = main(["sync", "--tracks-file", str(tracks_file), "--ack-consent"])
    assert code_ok == 0
    out = capsys.readouterr().out
    assert "Sincronización completada con éxito" in out


def test_cli_consent_subcommands(mock_cli_ipod: Path, capsys: pytest.CaptureFixture):
    # show inicial -> NO otorgado
    assert main(["consent", "show"]) == 0
    assert "NO otorgado" in capsys.readouterr().out

    # grant -> registrado
    assert main(["consent", "grant"]) == 0
    assert "registrado con éxito" in capsys.readouterr().out

    # show posterior -> OTORGADO
    assert main(["consent", "show"]) == 0
    assert "OTORGADO" in capsys.readouterr().out

    # revoke -> revocado
    assert main(["consent", "revoke"]) == 0
    assert "revocado" in capsys.readouterr().out


def test_cli_eject_bloqueador_sin_nombre_amigable_no_repite(
    mock_cli_ipod: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    # Regresión: un binario sin entrada en FRIENDLY_NAMES (p.ej. "zsh") no debe
    # imprimirse duplicado como "zsh (zsh)" — solo "zsh".
    from cicada.ipod.device.eject import Blocker, EjectResult

    fake_result = EjectResult(
        ejected=False,
        message="mensaje de prueba",
        blockers=(
            Blocker(pid=111, name="zsh"),
            Blocker(pid=222, name="Finder"),   # sí tiene friendly_name propio (igual al name)
            Blocker(pid=333, name="AMPDevicesAgent"),  # friendly_name distinto del name
        ),
    )
    monkeypatch.setattr("cicada.ipod.cli.eject_ipod", lambda *a, **k: fake_result)

    code = main(["eject"])
    assert code == 1
    out = capsys.readouterr().out
    assert "zsh (zsh)" not in out
    assert "Finder (Finder)" not in out
    assert "PID 111  zsh" in out
    assert "PID 222  Finder" in out
    assert "PID 333  Música (AMPDevicesAgent)" in out


def test_cli_sync_playback(mock_cli_ipod: Path, capsys: pytest.CaptureFixture):
    code = main(["sync-playback"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Pistas escaneadas :" in out
    assert "1" in out   # mock_cli_ipod tiene 1 pista

    from cicada.ipod.sync.state import SyncStateDB, default_sync_db_path
    db = SyncStateDB(default_sync_db_path())
    assert db.get_device(GUID_STR) is not None   # se auto-registró


def test_cli_sync_playback_dry_run_no_persiste(mock_cli_ipod: Path, capsys: pytest.CaptureFixture):
    code = main(["sync-playback", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "dry-run" in out

    from cicada.ipod.sync.state import SyncStateDB, default_sync_db_path
    db = SyncStateDB(default_sync_db_path())
    assert db.get_playback_state(GUID_STR, 100) is None   # no persistió línea base


def test_cli_backup_and_restore(mock_cli_ipod: Path, tmp_path: Path, capsys: pytest.CaptureFixture):
    # backup
    assert main(["backup"]) == 0
    out_backup = capsys.readouterr().out
    assert "Backup creado:" in out_backup
    backup_file = out_backup.split("Backup creado:")[1].strip()

    # list-backups
    assert main(["list-backups"]) == 0
    assert GUID_STR in capsys.readouterr().out

    # restore
    assert main(["restore", backup_file]) == 0
    assert "Restaurado" in capsys.readouterr().out
