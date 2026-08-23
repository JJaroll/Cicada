"""Tests para cicada/ipod/sync/conflicts.py — detección de conflictos de rating."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cicada.ipod.sync.conflicts import RatingConflict, resolve_conflicts, scan_for_conflicts
from cicada.ipod.sync.state import (
    DeviceRecord,
    LocalPlaybackStateRecord,
    PlaybackStateRecord,
    SyncStateDB,
    TrackMapRecord,
)

GUID = "000A27002484DDFB"


@pytest.fixture
def mock_ipod_dynamic(tmp_path: Path) -> Path:
    """iPod con 3 pistas en Dynamic.itdb: 101 (rating=80), 102 (rating=0), 103 (rating=60)."""
    mount = tmp_path / "ipod_mount"
    itlp = mount / "iPod_Control" / "iTunes" / "iTunes Library.itlp"
    itlp.mkdir(parents=True, exist_ok=True)

    db_path = itlp / "Dynamic.itdb"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE item_stats (
            item_pid INTEGER PRIMARY KEY,
            play_count_user INTEGER,
            play_count_recent INTEGER,
            user_rating INTEGER,
            date_played INTEGER,
            skip_count_user INTEGER,
            skip_count_recent INTEGER,
            date_skipped INTEGER
        );
        """
    )
    conn.execute(
        """
        INSERT INTO item_stats (item_pid, play_count_user, play_count_recent, user_rating, date_played, skip_count_user, skip_count_recent, date_skipped)
        VALUES (101, 0, 0, 80, 0, 0, 0, 0),
               (102, 0, 0, 0, 0, 0, 0, 0),
               (103, 0, 0, 60, 0, 0, 0, 0);
        """
    )
    conn.commit()
    conn.close()
    return mount


@pytest.fixture
def sync_db(tmp_path: Path) -> SyncStateDB:
    db = SyncStateDB(tmp_path / "ipod.db")
    db.upsert_device(DeviceRecord(guid=GUID))
    db.upsert_track_maps([
        TrackMapRecord(guid=GUID, ipod_dbid=101, local_path="/music/track1.mp3"),
        TrackMapRecord(guid=GUID, ipod_dbid=102, local_path="/music/track2.mp3"),
        TrackMapRecord(guid=GUID, ipod_dbid=103, local_path="/music/track3.mp3"),
    ])
    return db


def test_sin_baseline_no_es_conflicto(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=101, local_rating=40))
    result = scan_for_conflicts(mock_ipod_dynamic, sync_db, GUID)
    assert result.conflicts == []
    assert result.pending_local_pushes == []


def test_local_sin_cambios_no_es_nada(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=80))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=101, local_rating=80))
    result = scan_for_conflicts(mock_ipod_dynamic, sync_db, GUID)
    assert result.conflicts == []
    assert result.pending_local_pushes == []


def test_solo_local_cambio_es_pending_push(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=80))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=101, local_rating=40))

    result = scan_for_conflicts(mock_ipod_dynamic, sync_db, GUID)
    assert result.conflicts == []
    assert len(result.pending_local_pushes) == 1
    p = result.pending_local_pushes[0]
    assert p.ipod_dbid == 101
    assert p.local_rating == 40
    assert p.known_rating == 80
    assert p.local_path == "/music/track1.mp3"


def test_ambos_cambiaron_al_mismo_valor_es_pending_push_no_conflicto(
    mock_ipod_dynamic: Path, sync_db: SyncStateDB
):
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=50))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=101, local_rating=80))

    result = scan_for_conflicts(mock_ipod_dynamic, sync_db, GUID)
    assert result.conflicts == []
    assert len(result.pending_local_pushes) == 1


def test_conflicto_real_ambos_cambiaron_y_difieren(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=50))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=101, local_rating=20))

    result = scan_for_conflicts(mock_ipod_dynamic, sync_db, GUID)
    assert result.pending_local_pushes == []
    assert len(result.conflicts) == 1
    c = result.conflicts[0]
    assert c.ipod_dbid == 101
    assert c.known_rating == 50
    assert c.local_rating == 20
    assert c.device_rating == 80
    assert c.local_path == "/music/track1.mp3"
    assert result.has_conflicts is True


def test_scan_clasifica_varias_pistas_independientemente(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=50))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=101, local_rating=20))

    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=103, known_rating=60))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=103, local_rating=100))

    result = scan_for_conflicts(mock_ipod_dynamic, sync_db, GUID)
    assert {c.ipod_dbid for c in result.conflicts} == {101}
    assert {p.ipod_dbid for p in result.pending_local_pushes} == {103}


def test_pista_ausente_del_device_usa_known_como_device_rating(sync_db: SyncStateDB, tmp_path: Path):
    empty_mount = tmp_path / "empty_mount"
    (empty_mount / "iPod_Control" / "iTunes" / "iTunes Library.itlp").mkdir(parents=True)

    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=50))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=101, local_rating=20))

    result = scan_for_conflicts(empty_mount, sync_db, GUID)
    assert result.conflicts == []
    assert len(result.pending_local_pushes) == 1


@pytest.fixture
def real_ipod_two_tracks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    wasmtime = pytest.importorskip("wasmtime", reason="wasmtime no instalado")
    import plistlib

    from cicada.ipod.db.coordinator.plan import create_plan
    from cicada.ipod.db.models import TrackInfo
    from cicada.ipod.device.capabilities import capabilities_for_family_gen
    from cicada.ipod.device.checksum import ChecksumType
    from cicada.ipod.device.device_info import DeviceInfo

    mount = tmp_path / "ipod_mount"
    device_dir = mount / "iPod_Control" / "Device"
    device_dir.mkdir(parents=True)
    (device_dir / "SysInfoExtended").write_bytes(plistlib.dumps({
        "FireWireGUID": GUID, "FamilyID": 18,
        "SerialNumber": "C17X1234F19R", "ModelNumStr": "MD481",
    }))
    itunes_dir = mount / "iPod_Control" / "iTunes"
    itlp = itunes_dir / "iTunes Library.itlp"
    itlp.mkdir(parents=True)

    caps = capabilities_for_family_gen("iPod Nano", "7th Gen")
    dev = DeviceInfo(mount=mount, firewire_guid=GUID, family="iPod Nano",
                     generation="7th Gen", family_id=18, checksum=ChecksumType.HASHAB,
                     guid_provenance="disk", capabilities=caps)
    tracks = [
        TrackInfo(title="A", location=":iPod_Control:Music:F00:A.mp3", db_track_id=101, rating=80),
        TrackInfo(title="B", location=":iPod_Control:Music:F00:B.mp3", db_track_id=103, rating=60),
    ]
    plan = create_plan(mount, tracks, device_info=dev)
    (itunes_dir / "iTunesCDB").write_bytes((plan.staging_dir / "iTunesCDB").read_bytes())
    for fn in ("Library.itdb", "Locations.itdb", "Locations.itdb.cbk",
               "Dynamic.itdb", "Extras.itdb", "Genius.itdb"):
        (itlp / fn).write_bytes((plan.staging_dir / "iTunes Library.itlp" / fn).read_bytes())

    monkeypatch.setattr("cicada.ipod.device.write_guard._candidate_mounts", lambda: [mount])
    monkeypatch.setenv("CICADA_HOME", str(tmp_path / "cicada_home"))
    return mount, dev


def test_resolve_conflicts_local_gana_escribe_al_ipod(real_ipod_two_tracks, tmp_path: Path):
    from cicada.ipod.db.parser import load_ipod_library
    mount, dev = real_ipod_two_tracks
    sync_db = SyncStateDB(tmp_path / "cicada_home" / "ipod.db")
    sync_db.upsert_device(DeviceRecord(guid=GUID))
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=50))

    conflict = RatingConflict(guid=GUID, ipod_dbid=101, local_path=None,
                              known_rating=50, local_rating=20, device_rating=80)
    res = resolve_conflicts(mount, sync_db, [conflict], "local", device_info=dev, consent_ack=True)
    assert res.success is True

    lib = load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    track = next(t for t in lib["mhlt"] if t.get("db_track_id") == 101)
    assert track.get("rating") == 20

    assert sync_db.get_playback_state(GUID, 101).known_rating == 20
    assert sync_db.get_local_playback_state(GUID, 101).local_rating == 20


def test_resolve_conflicts_device_gana_no_escribe_al_ipod(real_ipod_two_tracks, tmp_path: Path):
    from cicada.ipod.db.parser import load_ipod_library
    mount, dev = real_ipod_two_tracks
    sync_db = SyncStateDB(tmp_path / "cicada_home" / "ipod.db")
    sync_db.upsert_device(DeviceRecord(guid=GUID))
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=50))

    conflict = RatingConflict(guid=GUID, ipod_dbid=101, local_path=None,
                              known_rating=50, local_rating=20, device_rating=80)
    res = resolve_conflicts(mount, sync_db, [conflict], "device", device_info=dev, consent_ack=False)
    assert res.success is True

    lib = load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    track = next(t for t in lib["mhlt"] if t.get("db_track_id") == 101)
    assert track.get("rating") == 80

    assert sync_db.get_playback_state(GUID, 101).known_rating == 80
    assert sync_db.get_local_playback_state(GUID, 101).local_rating == 80


def test_resolve_conflicts_batch_una_sola_escritura(real_ipod_two_tracks, tmp_path: Path):
    from cicada.ipod.db.parser import load_ipod_library
    mount, dev = real_ipod_two_tracks
    sync_db = SyncStateDB(tmp_path / "cicada_home" / "ipod.db")
    sync_db.upsert_device(DeviceRecord(guid=GUID))
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=50))
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=103, known_rating=30))

    conflicts = [
        RatingConflict(guid=GUID, ipod_dbid=101, local_path=None, known_rating=50, local_rating=20, device_rating=80),
        RatingConflict(guid=GUID, ipod_dbid=103, local_path=None, known_rating=30, local_rating=100, device_rating=60),
    ]
    res = resolve_conflicts(mount, sync_db, conflicts, "local", device_info=dev, consent_ack=True)
    assert res.success is True
    assert res.tracks_written == 2

    lib = load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    ratings = {t.get("db_track_id"): t.get("rating") for t in lib["mhlt"]}
    assert ratings[101] == 20
    assert ratings[103] == 100


def test_resolve_conflicts_lista_vacia_no_hace_nada(real_ipod_two_tracks, tmp_path: Path):
    mount, dev = real_ipod_two_tracks
    sync_db = SyncStateDB(tmp_path / "cicada_home" / "ipod.db")
    res = resolve_conflicts(mount, sync_db, [], "local", device_info=dev, consent_ack=True)
    assert res.success is True
    assert res.tracks_written == 0


def test_resolve_conflicts_resolution_invalida(real_ipod_two_tracks, tmp_path: Path):
    mount, dev = real_ipod_two_tracks
    sync_db = SyncStateDB(tmp_path / "cicada_home" / "ipod.db")
    conflict = RatingConflict(guid=GUID, ipod_dbid=101, local_path=None,
                              known_rating=50, local_rating=20, device_rating=80)
    with pytest.raises(ValueError):
        resolve_conflicts(mount, sync_db, [conflict], "coinflip", device_info=dev, consent_ack=True)
