"""Tests para cicada/ipod/sync/conflicts.py — detección de conflictos de rating."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cicada.ipod.sync.conflicts import scan_for_conflicts
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
    # local diverge, pero no hay known_rating (primer sync) -> se ignora,
    # no hay "cambio desde el último sync" que evaluar.
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=101, local_rating=40))
    result = scan_for_conflicts(mock_ipod_dynamic, sync_db, GUID)
    assert result.conflicts == []
    assert result.pending_local_pushes == []


def test_local_sin_cambios_no_es_nada(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    # local == known: el usuario no tocó nada localmente.
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=80))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=101, local_rating=80))
    result = scan_for_conflicts(mock_ipod_dynamic, sync_db, GUID)
    assert result.conflicts == []
    assert result.pending_local_pushes == []


def test_solo_local_cambio_es_pending_push(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    # known=50 (baseline), device sigue en 80 (== baseline original del device,
    # simulemos que el device nunca cambió: known coincide con lo leído).
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=80))
    # El usuario calificó distinto en Cicada.
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
    # known=50, device (leído)=80, local=80 -> coinciden entre sí, no hay desacuerdo.
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=50))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=101, local_rating=80))

    result = scan_for_conflicts(mock_ipod_dynamic, sync_db, GUID)
    assert result.conflicts == []
    assert len(result.pending_local_pushes) == 1


def test_conflicto_real_ambos_cambiaron_y_difieren(mock_ipod_dynamic: Path, sync_db: SyncStateDB):
    # known=50, device (leído)=80, local=20 -> los tres distintos: conflicto real.
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
    # 101: conflicto real. 103: solo local cambió (device sigue en su known).
    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=50))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=101, local_rating=20))

    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=103, known_rating=60))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=103, local_rating=100))

    result = scan_for_conflicts(mock_ipod_dynamic, sync_db, GUID)
    assert {c.ipod_dbid for c in result.conflicts} == {101}
    assert {p.ipod_dbid for p in result.pending_local_pushes} == {103}


def test_pista_ausente_del_device_usa_known_como_device_rating(sync_db: SyncStateDB, tmp_path: Path):
    # Si la pista ya no está en el iPod (p.ej. se borró), no debe crashear:
    # se trata como si el device no hubiera cambiado (known_rating).
    empty_mount = tmp_path / "empty_mount"
    (empty_mount / "iPod_Control" / "iTunes" / "iTunes Library.itlp").mkdir(parents=True)

    sync_db.upsert_playback_state(PlaybackStateRecord(guid=GUID, ipod_dbid=101, known_rating=50))
    sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(guid=GUID, ipod_dbid=101, local_rating=20))

    result = scan_for_conflicts(empty_mount, sync_db, GUID)
    assert result.conflicts == []
    assert len(result.pending_local_pushes) == 1   # tratado como "solo local cambió"
