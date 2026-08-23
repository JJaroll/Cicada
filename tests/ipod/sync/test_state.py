"""Tests para cicada/ipod/sync/state.py — Persistencia local de sincronización."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cicada.ipod.sync.state import (
    DeviceRecord,
    LocalPlaybackStateRecord,
    PlaybackStateRecord,
    PlaylistMapRecord,
    SyncStateDB,
    TrackMapRecord,
)

GUID_1 = "000A27002484DDFB"
GUID_2 = "000A270011223344"


@pytest.fixture
def sync_db(tmp_path: Path) -> SyncStateDB:
    db_file = tmp_path / "test_ipod.db"
    return SyncStateDB(db_file)


def test_init_schema_creates_tables(sync_db: SyncStateDB):
    """Verifica que se inicializan las 5 tablas e índices requeridos."""
    with sync_db._connection() as conn:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        assert "devices" in tables
        assert "track_map" in tables
        assert "playback_state" in tables
        assert "playlists_map" in tables
        assert "local_playback_state" in tables


def test_device_upsert_and_retrieve(sync_db: SyncStateDB):
    """Prueba upsert, consulta y listado de dispositivos."""
    dev = DeviceRecord(
        guid=GUID_1,
        family_id=18,
        model_num="MD481",
        serial="C17X1234F19R",
        name="Mi iPod Nano",
        first_seen=1700000000,
        last_seen=1700000100,
    )
    sync_db.upsert_device(dev)

    retrieved = sync_db.get_device(GUID_1)
    assert retrieved is not None
    assert retrieved.guid == GUID_1
    assert retrieved.model_num == "MD481"
    assert retrieved.name == "Mi iPod Nano"

    dev.last_seen = 1700000999
    sync_db.upsert_device(dev)
    updated = sync_db.get_device(GUID_1)
    assert updated is not None
    assert updated.last_seen == 1700000999

    devs = sync_db.list_devices()
    assert len(devs) == 1
    assert devs[0].guid == GUID_1


def test_track_map_u64_id_normalization(sync_db: SyncStateDB):
    """Verifica que los IDs grandes que superan 2^63-1 se recuperan correctamente como uint64."""
    sync_db.upsert_device(DeviceRecord(guid=GUID_1))

    large_dbid_1 = 0xFFFFFFFFFFFFFFFF
    large_dbid_2 = 0x9000000000000001

    rec1 = TrackMapRecord(
        guid=GUID_1,
        ipod_dbid=large_dbid_1,
        local_path="/music/song1.mp3",
        local_mtime=16000000.0,
        local_size=10240,
        ipod_relpath=":iPod_Control:Music:F00:S1.mp3",
    )
    rec2 = TrackMapRecord(
        guid=GUID_1,
        ipod_dbid=large_dbid_2,
        local_path="/music/song2.mp3",
        local_mtime=16000001.0,
        local_size=20480,
        ipod_relpath=":iPod_Control:Music:F01:S2.mp3",
    )

    sync_db.upsert_track_maps([rec1, rec2])

    t1 = sync_db.get_track_map(GUID_1, large_dbid_1)
    assert t1 is not None
    assert t1.ipod_dbid == large_dbid_1
    assert t1.local_path == "/music/song1.mp3"

    t2 = sync_db.get_track_map_by_local_path(GUID_1, "/music/song2.mp3")
    assert t2 is not None
    assert t2.ipod_dbid == large_dbid_2

    all_tracks = sync_db.list_track_maps(GUID_1)
    assert len(all_tracks) == 2

    deleted = sync_db.delete_track_maps(GUID_1, [large_dbid_1])
    assert deleted == 1
    assert sync_db.get_track_map(GUID_1, large_dbid_1) is None
    assert sync_db.get_track_map(GUID_1, large_dbid_2) is not None


def test_playback_state_stars_property(sync_db: SyncStateDB):
    """Verifica el cálculo de estrellas a partir de la calificación 0-100."""
    sync_db.upsert_device(DeviceRecord(guid=GUID_1))

    ratings = [(101, 0, 0), (102, 20, 1), (103, 60, 3), (104, 80, 4), (105, 100, 5)]
    records = [
        PlaybackStateRecord(
            guid=GUID_1,
            ipod_dbid=dbid,
            known_rating=rating,
            known_play_count=5,
            known_last_played=1700000000,
        )
        for dbid, rating, _ in ratings
    ]
    sync_db.upsert_playback_states(records)

    for dbid, rating, expected_stars in ratings:
        pb = sync_db.get_playback_state(GUID_1, dbid)
        assert pb is not None
        assert pb.known_rating == rating
        assert pb.stars == expected_stars


def test_playback_state_bulk_and_mapping(sync_db: SyncStateDB):
    """Verifica get_all_playback_states indexado por uint64."""
    sync_db.upsert_device(DeviceRecord(guid=GUID_1))

    large_id = 0x8000000000000005
    recs = [
        PlaybackStateRecord(guid=GUID_1, ipod_dbid=1, known_play_count=3),
        PlaybackStateRecord(guid=GUID_1, ipod_dbid=large_id, known_play_count=10),
    ]
    sync_db.upsert_playback_states(recs)

    mapping = sync_db.get_all_playback_states(GUID_1)
    assert len(mapping) == 2
    assert 1 in mapping
    assert large_id in mapping
    assert mapping[large_id].known_play_count == 10


def test_local_playback_state_stars_property(sync_db: SyncStateDB):
    """Espejo de test_playback_state_stars_property, para local_rating."""
    sync_db.upsert_device(DeviceRecord(guid=GUID_1))

    ratings = [(101, 0, 0), (102, 20, 1), (103, 60, 3), (104, 80, 4), (105, 100, 5)]
    records = [
        LocalPlaybackStateRecord(guid=GUID_1, ipod_dbid=dbid, local_rating=rating)
        for dbid, rating, _ in ratings
    ]
    sync_db.upsert_local_playback_states(records)

    for dbid, rating, expected_stars in ratings:
        lp = sync_db.get_local_playback_state(GUID_1, dbid)
        assert lp is not None
        assert lp.local_rating == rating
        assert lp.stars == expected_stars


def test_local_playback_state_bulk_and_mapping(sync_db: SyncStateDB):
    """Espejo de test_playback_state_bulk_and_mapping, para local_playback_state."""
    sync_db.upsert_device(DeviceRecord(guid=GUID_1))

    large_id = 0x8000000000000005
    recs = [
        LocalPlaybackStateRecord(guid=GUID_1, ipod_dbid=1, local_rating=40),
        LocalPlaybackStateRecord(guid=GUID_1, ipod_dbid=large_id, local_rating=100),
    ]
    sync_db.upsert_local_playback_states(recs)

    mapping = sync_db.get_all_local_playback_states(GUID_1)
    assert len(mapping) == 2
    assert 1 in mapping
    assert large_id in mapping
    assert mapping[large_id].local_rating == 100


def test_local_playback_state_upsert_actualiza_no_duplica(sync_db: SyncStateDB):
    sync_db.upsert_device(DeviceRecord(guid=GUID_1))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID_1, ipod_dbid=1, local_rating=40))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID_1, ipod_dbid=1, local_rating=100))

    assert sync_db.get_local_playback_state(GUID_1, 1).local_rating == 100
    assert len(sync_db.get_all_local_playback_states(GUID_1)) == 1


def test_atomic_transaction_and_rollback(sync_db: SyncStateDB):
    """Verifica que transaction() revierte en caso de excepción."""
    sync_db.upsert_device(DeviceRecord(guid=GUID_1))

    with pytest.raises(RuntimeError):
        with sync_db.transaction() as conn:
            sync_db.upsert_track_map(
                TrackMapRecord(
                    guid=GUID_1,
                    ipod_dbid=1001,
                    local_path="/music/will_rollback.mp3",
                ),
                conn=conn,
            )
            raise RuntimeError("Error forzado para disparar rollback")

    assert sync_db.get_track_map(GUID_1, 1001) is None


def test_cascade_delete_on_device_removal(sync_db: SyncStateDB):
    """Verifica borrado en cascada de track_map, playback_state y playlists_map al eliminar un dispositivo."""
    sync_db.upsert_device(DeviceRecord(guid=GUID_1))

    sync_db.upsert_track_map(TrackMapRecord(guid=GUID_1, ipod_dbid=501, local_path="/m/1.mp3"))
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID_1, ipod_dbid=501, known_play_count=2))
    sync_db.upsert_playlist_map(PlaylistMapRecord(guid=GUID_1, playlist_id=701, name="Rock"))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID_1, ipod_dbid=501, local_rating=60))

    assert sync_db.get_track_map(GUID_1, 501) is not None
    assert sync_db.get_playback_state(GUID_1, 501) is not None
    assert len(sync_db.list_playlists_map(GUID_1)) == 1
    assert sync_db.get_local_playback_state(GUID_1, 501) is not None

    with sync_db._connection() as conn:
        conn.execute("DELETE FROM devices WHERE guid = ?", (GUID_1,))
        conn.commit()

    assert sync_db.get_track_map(GUID_1, 501) is None
    assert sync_db.get_playback_state(GUID_1, 501) is None
    assert len(sync_db.list_playlists_map(GUID_1)) == 0
    assert sync_db.get_local_playback_state(GUID_1, 501) is None
