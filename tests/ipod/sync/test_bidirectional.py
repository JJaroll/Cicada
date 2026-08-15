"""Tests para cicada/ipod/sync/bidirectional.py — Sincronización bidireccional de reproducciones."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cicada.ipod.db.sqlite._helpers import CORE_DATA_EPOCH, coredata_to_unix
from cicada.ipod.sync.bidirectional import (
    PlaybackDeltaReport,
    RawPlaybackStat,
    TrackPlaybackDelta,
    commit_playback_deltas,
    compute_playback_deltas,
    read_ipod_playback_stats,
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
            pid INTEGER PRIMARY KEY,
            play_count_user INTEGER,
            play_count_recent INTEGER,
            rating INTEGER,
            date_played INTEGER,
            skip_count_user INTEGER,
            skip_count_recent INTEGER,
            date_skipped INTEGER
        );
        """
    )
    # Track 1: pid=101, plays=5+3=8, rating=80 (4 estrellas), played=1000s Cocoa
    # Track 2: pid=102, plays=2+0=2, rating=0, played=0
    # Track 3: pid=103, plays=0, rating=100 (5 estrellas), skips=1+2=3, skipped=500s Cocoa
    conn.execute(
        """
        INSERT INTO item_stats (pid, play_count_user, play_count_recent, rating, date_played, skip_count_user, skip_count_recent, date_skipped)
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
    assert report.total_delta_plays == 10  # 8 (track 101) + 2 (track 102)
    assert report.total_delta_skips == 3   # 3 (track 103)
    assert report.ratings_updated_count == 2  # track 101 (80) y track 103 (100)

    # Validar que local_path se resolvió
    t101 = next(t for t in report.tracks_with_deltas if t.ipod_dbid == 101)
    assert t101.local_path == "/music/track1.mp3"
    assert t101.delta_play_count == 8
    assert t101.current_play_count == 8
    assert t101.new_stars == 4


def test_compute_deltas_incremental_plays(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    # Baseline: track 101 tenía 5 plays y rating 80
    sync_db.upsert_playback_state(
        PlaybackStateRecord(
            guid=GUID,
            ipod_dbid=101,
            known_play_count=5,
            known_rating=80,
            known_last_played=1000 + CORE_DATA_EPOCH,
        )
    )
    # Baseline: track 102 tenía 2 plays
    sync_db.upsert_playback_state(
        PlaybackStateRecord(
            guid=GUID,
            ipod_dbid=102,
            known_play_count=2,
            known_rating=0,
        )
    )
    # Baseline: track 103 tenía rating 100 y 3 skips
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
    # Solo track 101 tiene delta (+3 plays)
    assert len(report.tracks_with_deltas) == 1
    t101 = report.tracks_with_deltas[0]
    assert t101.ipod_dbid == 101
    assert t101.delta_play_count == 3
    assert t101.current_play_count == 8
    assert t101.rating_changed is False
    assert report.total_delta_plays == 3
    assert report.total_delta_skips == 0


def test_compute_deltas_rating_modification(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    # Baseline: track 101 tenía 8 plays pero rating 40 (2 estrellas)
    sync_db.upsert_playback_state(
        PlaybackStateRecord(
            guid=GUID,
            ipod_dbid=101,
            known_play_count=8,
            known_rating=40,
            known_last_played=1000 + CORE_DATA_EPOCH,
        )
    )
    # Baseline: tracks 102 y 103 al día
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
    # Baseline: track 101 tenía 20 plays (en el iPod ahora hay 8)
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
    # Se detecta el cambio para actualizar la línea base, pero sin delta positivo hacia la biblioteca
    assert report.has_changes is True
    assert len(report.tracks_with_deltas) == 1
    t101 = report.tracks_with_deltas[0]
    assert t101.delta_play_count == 0
    assert t101.current_play_count == 8
    assert report.total_delta_plays == 0


def test_commit_playback_deltas_idempotent(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    # 1. Primer cálculo (sin baseline)
    report1 = compute_playback_deltas(mock_ipod_dynamic, sync_db, GUID)
    assert report1.has_changes is True
    assert report1.total_delta_plays == 10

    # 2. Aplicar y guardar baseline
    commit_playback_deltas(report1, sync_db)

    # 3. Validar estado en sync_db
    p103 = sync_db.get_playback_state(GUID, 103)
    assert p103 is not None
    assert p103.known_skip_count == 3
    assert p103.known_rating == 100

    # 4. Segundo cálculo -> cero cambios pendientes
    report2 = compute_playback_deltas(mock_ipod_dynamic, sync_db, GUID)
    assert report2.has_changes is False
    assert len(report2.tracks_with_deltas) == 0
    assert report2.total_delta_plays == 0
    assert report2.total_delta_skips == 0
