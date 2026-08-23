"""Tests para cicada/ipod/sync/bidirectional.py — Sincronización bidireccional de reproducciones."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from cicada.ipod.db.sqlite._helpers import CORE_DATA_EPOCH, coredata_to_unix
from cicada.ipod.sync.bidirectional import (
    PlaybackDeltaReport,
    RawPlaybackStat,
    TrackPlaybackDelta,
    commit_playback_deltas,
    compute_playback_deltas,
    read_ipod_playback_stats,
    sync_playback_stats,
)
from cicada.ipod.sync.state import (
    DeviceRecord,
    PlaybackStateRecord,
    SyncStateDB,
    TrackMapRecord,
)

GUID = "000A27002484DDFB"


@pytest.fixture
def mock_ipod_dynamic(tmp_path: Path) -> Path:
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
        VALUES
            (101, 5, 3, 80, 1000, 0, 0, 0),
            (102, 2, 0, 0, 0, 0, 0, 0),
            (103, 0, 0, 100, 0, 1, 2, 500);
        """
    )
    conn.commit()
    conn.close()
    return mount


@pytest.fixture
def sync_db(tmp_path: Path) -> SyncStateDB:
    db = SyncStateDB(tmp_path / "ipod.db")
    db.upsert_device(DeviceRecord(guid=GUID))
    db.upsert_track_maps(
        [
            TrackMapRecord(guid=GUID, ipod_dbid=101, local_path="/music/track1.mp3"),
            TrackMapRecord(guid=GUID, ipod_dbid=102, local_path="/music/track2.mp3"),
            TrackMapRecord(guid=GUID, ipod_dbid=103, local_path="/music/track3.mp3"),
        ]
    )
    return db


def test_coredata_to_unix_helper():
    assert coredata_to_unix(0) == 0
    assert coredata_to_unix(100) == 100 + CORE_DATA_EPOCH


def test_read_playback_stats_from_dynamic_itdb(mock_ipod_dynamic: Path):
    stats = read_ipod_playback_stats(mock_ipod_dynamic)
    assert len(stats) == 3

    s101 = stats[101]
    assert s101.ipod_dbid == 101
    assert s101.play_count == 8
    assert s101.rating == 80
    assert s101.last_played == 1000 + CORE_DATA_EPOCH
    assert s101.skip_count == 0

    s103 = stats[103]
    assert s103.play_count == 0
    assert s103.rating == 100
    assert s103.skip_count == 3
    assert s103.date_skipped == 500 + CORE_DATA_EPOCH


def test_compute_deltas_fresh_device(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    report = compute_playback_deltas(mock_ipod_dynamic, sync_db, GUID)
    assert report.guid == GUID
    assert report.total_tracks_scanned == 3
    assert report.has_changes is True
    assert report.total_delta_plays == 10
    assert report.total_delta_skips == 3
    assert report.ratings_updated_count == 2

    t101 = next(t for t in report.tracks_with_deltas if t.ipod_dbid == 101)
    assert t101.local_path == "/music/track1.mp3"
    assert t101.delta_play_count == 8
    assert t101.current_play_count == 8
    assert t101.new_stars == 4


def test_compute_deltas_incremental_plays(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    sync_db.upsert_playback_state(
        PlaybackStateRecord(
            guid=GUID,
            ipod_dbid=101,
            known_play_count=5,
            known_rating=80,
            known_last_played=1000 + CORE_DATA_EPOCH,
        )
    )
    sync_db.upsert_playback_state(
        PlaybackStateRecord(
            guid=GUID,
            ipod_dbid=102,
            known_play_count=2,
            known_rating=0,
        )
    )
    sync_db.upsert_playback_state(
        PlaybackStateRecord(
            guid=GUID,
            ipod_dbid=103,
            known_play_count=0,
            known_rating=100,
            known_skip_count=3,
        )
    )

    report = compute_playback_deltas(mock_ipod_dynamic, sync_db, GUID)
    assert report.has_changes is True
    assert len(report.tracks_with_deltas) == 1
    t101 = report.tracks_with_deltas[0]
    assert t101.ipod_dbid == 101
    assert t101.delta_play_count == 3
    assert t101.current_play_count == 8
    assert t101.rating_changed is False
    assert report.total_delta_plays == 3
    assert report.total_delta_skips == 0


def test_compute_deltas_rating_modification(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    sync_db.upsert_playback_state(
        PlaybackStateRecord(
            guid=GUID,
            ipod_dbid=101,
            known_play_count=8,
            known_rating=40,
            known_last_played=1000 + CORE_DATA_EPOCH,
        )
    )
    sync_db.upsert_playback_states(
        [
            PlaybackStateRecord(guid=GUID, ipod_dbid=102, known_play_count=2),
            PlaybackStateRecord(guid=GUID, ipod_dbid=103, known_play_count=0, known_rating=100, known_skip_count=3),
        ]
    )

    report = compute_playback_deltas(mock_ipod_dynamic, sync_db, GUID)
    assert report.has_changes is True
    assert len(report.tracks_with_deltas) == 1
    t101 = report.tracks_with_deltas[0]
    assert t101.rating_changed is True
    assert t101.delta_play_count == 0
    assert t101.new_rating == 80
    assert t101.new_stars == 4


def test_compute_deltas_counter_reset_protection(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    sync_db.upsert_playback_state(
        PlaybackStateRecord(
            guid=GUID,
            ipod_dbid=101,
            known_play_count=20,
            known_rating=80,
            known_last_played=1000 + CORE_DATA_EPOCH,
        )
    )
    sync_db.upsert_playback_states(
        [
            PlaybackStateRecord(guid=GUID, ipod_dbid=102, known_play_count=2),
            PlaybackStateRecord(guid=GUID, ipod_dbid=103, known_play_count=0, known_rating=100, known_skip_count=3),
        ]
    )

    report = compute_playback_deltas(mock_ipod_dynamic, sync_db, GUID)
    assert report.has_changes is True
    assert len(report.tracks_with_deltas) == 1
    t101 = report.tracks_with_deltas[0]
    assert t101.delta_play_count == 0
    assert t101.current_play_count == 8
    assert report.total_delta_plays == 0


def test_commit_playback_deltas_idempotent(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    report1 = compute_playback_deltas(mock_ipod_dynamic, sync_db, GUID)
    assert report1.has_changes is True
    assert report1.total_delta_plays == 10

    commit_playback_deltas(report1, sync_db)

    p103 = sync_db.get_playback_state(GUID, 103)
    assert p103 is not None
    assert p103.known_skip_count == 3
    assert p103.known_rating == 100

    report2 = compute_playback_deltas(mock_ipod_dynamic, sync_db, GUID)
    assert report2.has_changes is False
    assert len(report2.tracks_with_deltas) == 0
    assert report2.total_delta_plays == 0
    assert report2.total_delta_skips == 0


def _fake_device_info(guid=GUID):
    return SimpleNamespace(
        firewire_guid=guid, family_id=18, model_number="MD481",
        serial="C17X1234F19R", family="iPod Nano", generation="7th Gen",
    )


def test_sync_playback_stats_registra_device_automaticamente(mock_ipod_dynamic: Path, tmp_path: Path):
    db = SyncStateDB(tmp_path / "ipod_sin_device.db")
    assert db.get_device(GUID) is None

    report = sync_playback_stats(mock_ipod_dynamic, _fake_device_info(), sync_db=db)

    assert report.has_changes is True
    assert db.get_device(GUID) is not None
    assert db.get_device(GUID).model_num == "MD481"
    assert db.get_playback_state(GUID, 103) is not None


def test_sync_playback_stats_idempotente(mock_ipod_dynamic: Path, tmp_path: Path):
    db = SyncStateDB(tmp_path / "ipod.db")
    report1 = sync_playback_stats(mock_ipod_dynamic, _fake_device_info(), sync_db=db)
    assert report1.has_changes is True

    report2 = sync_playback_stats(mock_ipod_dynamic, _fake_device_info(), sync_db=db)
    assert report2.has_changes is False


def test_compute_deltas_no_commitea_rating_si_local_tambien_diverge(
    mock_ipod_dynamic: Path, sync_db: SyncStateDB
):
    from cicada.ipod.sync.state import LocalPlaybackStateRecord

    sync_db.upsert_playback_state(
        PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_play_count=8,
                            known_rating=50, known_skip_count=0)
    )
    sync_db.upsert_local_playback_state(
        LocalPlaybackStateRecord(guid=GUID, ipod_dbid=101, local_rating=20)
    )

    report = compute_playback_deltas(mock_ipod_dynamic, sync_db, GUID)
    t101 = next(t for t in report.tracks_with_deltas if t.ipod_dbid == 101)
    assert t101.rating_changed is False
    assert t101.new_rating == 50

    commit_playback_deltas(report, sync_db)
    assert sync_db.get_playback_state(GUID, 101).known_rating == 50


def test_sync_playback_stats_default_sync_db(mock_ipod_dynamic: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CICADA_HOME", str(tmp_path / "cicada_home"))
    report = sync_playback_stats(mock_ipod_dynamic, _fake_device_info())
    assert report.has_changes is True
    assert (tmp_path / "cicada_home" / "ipod.db").is_file()


@pytest.fixture
def real_nano7g_device(tmp_path: Path):
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
    tracks = [TrackInfo(title="Track Real", location=":iPod_Control:Music:F00:R.mp3",
                        db_track_id=555, rating=80, play_count=5)]
    plan = create_plan(mount, tracks, device_info=dev)

    (itunes_dir / "iTunesCDB").write_bytes((plan.staging_dir / "iTunesCDB").read_bytes())
    for fn in ("Library.itdb", "Locations.itdb", "Locations.itdb.cbk",
               "Dynamic.itdb", "Extras.itdb", "Genius.itdb"):
        (itlp / fn).write_bytes((plan.staging_dir / "iTunes Library.itlp" / fn).read_bytes())
    return mount


def test_read_stats_contra_escritor_real_nano7g(real_nano7g_device: Path):
    stats = read_ipod_playback_stats(real_nano7g_device)
    assert 555 in stats
    assert stats[555].rating == 80
    assert stats[555].play_count == 5


def test_sync_playback_stats_contra_escritor_real_nano7g(real_nano7g_device: Path, tmp_path: Path):
    db = SyncStateDB(tmp_path / "ipod.db")
    report = sync_playback_stats(real_nano7g_device, _fake_device_info(), sync_db=db)
    assert report.has_changes is True
    assert report.ratings_updated_count == 1
    assert db.get_playback_state(GUID, 555).known_rating == 80
