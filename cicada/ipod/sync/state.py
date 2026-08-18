"""Gestión del estado persistente local en SQLite (~/.cicada/ipod.db) — Fase 3.

Mantiene:
- Registro de dispositivos iPod conocidos (tabla ``devices``).
- Mapeo bidireccional entre rutas locales y PIDs del iPod (tabla ``track_map``).
- Línea base de contadores de reproducción para deltas (tabla ``playback_state``).
- Mapeo de listas de reproducción sincronizadas (tabla ``playlists_map``).
"""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from cicada.ipod.db.sqlite._helpers import s64, u64


def default_sync_db_path() -> Path:
    """Ruta por defecto de la base de datos local (~/.cicada/ipod.db o $CICADA_HOME/ipod.db)."""
    base = Path(os.environ.get("CICADA_HOME") or (Path.home() / ".cicada"))
    return base / "ipod.db"


# ═══════════════════════════════════════════════════════════════════════════
# Modelos / Dataclasses de Repositorio
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DeviceRecord:
    guid: str
    family_id: Optional[int] = None
    model_num: Optional[str] = None
    serial: Optional[str] = None
    name: Optional[str] = None
    first_seen: int = 0
    last_seen: int = 0


@dataclass
class TrackMapRecord:
    guid: str
    ipod_dbid: int  # uint64 normalizado
    local_path: str
    local_mtime: float = 0.0
    local_size: int = 0
    content_hash: Optional[str] = None
    ipod_relpath: str = ""
    transcoded: int = 0
    source_codec: Optional[str] = None
    synced_at: int = 0


@dataclass
class PlaybackStateRecord:
    guid: str
    ipod_dbid: int  # uint64 normalizado
    known_play_count: int = 0
    known_rating: int = 0  # 0 a 100 (canónico iPod: 20 por estrella)
    known_last_played: int = 0  # Unix timestamp 1970
    known_skip_count: int = 0
    known_date_skipped: int = 0  # Unix timestamp 1970
    synced_at: int = 0

    @property
    def stars(self) -> int:
        """Convierte la calificación 0-100 a escala 0-5 estrellas."""
        return max(0, min(5, self.known_rating // 20))


@dataclass
class PlaylistMapRecord:
    guid: str
    playlist_id: int  # uint64 normalizado
    name: str
    is_smart: bool = False
    track_count: int = 0
    synced_at: int = 0


@dataclass
class LocalPlaybackStateRecord:
    """Rating asignado desde Cicada (independiente del dispositivo) — el
    tercer punto de datos para detectar conflictos de verdad: si diverge
    tanto del baseline (``playback_state.known_rating``) como del valor
    actual del iPod, y ambos lados difieren entre sí, es un conflicto."""
    guid: str
    ipod_dbid: int  # uint64 normalizado
    local_rating: int = 0  # 0 a 100 (canónico iPod: 20 por estrella)
    updated_at: int = 0

    @property
    def stars(self) -> int:
        return max(0, min(5, self.local_rating // 20))


# ═══════════════════════════════════════════════════════════════════════════
# Repositorio SQLite
# ═══════════════════════════════════════════════════════════════════════════

class SyncStateDB:
    """Acceso y persistencia transaccional a ~/.cicada/ipod.db."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path is not None else default_sync_db_path()
        self._init_db()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Crea una conexión con cierre garantizado (try/finally: conn.close())."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Crea las tablas e índices si no existen."""
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    guid TEXT PRIMARY KEY,
                    family_id INTEGER,
                    model_num TEXT,
                    serial TEXT,
                    name TEXT,
                    first_seen INTEGER NOT NULL,
                    last_seen INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS track_map (
                    guid TEXT NOT NULL,
                    ipod_dbid INTEGER NOT NULL,
                    local_path TEXT NOT NULL,
                    local_mtime REAL,
                    local_size INTEGER,
                    content_hash TEXT,
                    ipod_relpath TEXT NOT NULL,
                    transcoded INTEGER DEFAULT 0,
                    source_codec TEXT,
                    synced_at INTEGER NOT NULL,
                    PRIMARY KEY (guid, ipod_dbid),
                    FOREIGN KEY (guid) REFERENCES devices(guid) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_track_map_local ON track_map(guid, local_path);

                CREATE TABLE IF NOT EXISTS playback_state (
                    guid TEXT NOT NULL,
                    ipod_dbid INTEGER NOT NULL,
                    known_play_count INTEGER DEFAULT 0,
                    known_rating INTEGER DEFAULT 0,
                    known_last_played INTEGER DEFAULT 0,
                    known_skip_count INTEGER DEFAULT 0,
                    known_date_skipped INTEGER DEFAULT 0,
                    synced_at INTEGER NOT NULL,
                    PRIMARY KEY (guid, ipod_dbid),
                    FOREIGN KEY (guid) REFERENCES devices(guid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS playlists_map (
                    guid TEXT NOT NULL,
                    playlist_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    is_smart INTEGER DEFAULT 0,
                    track_count INTEGER DEFAULT 0,
                    synced_at INTEGER NOT NULL,
                    PRIMARY KEY (guid, playlist_id),
                    FOREIGN KEY (guid) REFERENCES devices(guid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS local_playback_state (
                    guid TEXT NOT NULL,
                    ipod_dbid INTEGER NOT NULL,
                    local_rating INTEGER DEFAULT 0,
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY (guid, ipod_dbid),
                    FOREIGN KEY (guid) REFERENCES devices(guid) ON DELETE CASCADE
                );
                """
            )
            conn.commit()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Gestor de contexto para transacciones atómicas explícitas con cierre garantizado."""
        with self._connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE;")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    # ── Devices ────────────────────────────────────────────────────────────

    def upsert_device(self, dev: DeviceRecord, conn: Optional[sqlite3.Connection] = None) -> None:
        now = int(time.time())
        first = dev.first_seen or now
        last = dev.last_seen or now

        def _do_work(c: sqlite3.Connection):
            c.execute(
                """
                INSERT INTO devices (guid, family_id, model_num, serial, name, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guid) DO UPDATE SET
                    family_id = excluded.family_id,
                    model_num = excluded.model_num,
                    serial = excluded.serial,
                    name = coalesce(excluded.name, devices.name),
                    last_seen = excluded.last_seen;
                """,
                (dev.guid, dev.family_id, dev.model_num, dev.serial, dev.name, first, last),
            )
            if conn is None:
                c.commit()

        if conn is not None:
            _do_work(conn)
        else:
            with self._connection() as c:
                _do_work(c)

    def get_device(self, guid: str) -> Optional[DeviceRecord]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM devices WHERE guid = ?", (guid,)).fetchone()
            if not row:
                return None
            return DeviceRecord(
                guid=row["guid"],
                family_id=row["family_id"],
                model_num=row["model_num"],
                serial=row["serial"],
                name=row["name"],
                first_seen=row["first_seen"],
                last_seen=row["last_seen"],
            )

    def list_devices(self) -> List[DeviceRecord]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
            return [
                DeviceRecord(
                    guid=r["guid"],
                    family_id=r["family_id"],
                    model_num=r["model_num"],
                    serial=r["serial"],
                    name=r["name"],
                    first_seen=r["first_seen"],
                    last_seen=r["last_seen"],
                )
                for r in rows
            ]

    # ── Track Map ──────────────────────────────────────────────────────────

    def upsert_track_map(self, rec: TrackMapRecord, conn: Optional[sqlite3.Connection] = None) -> None:
        self.upsert_track_maps([rec], conn=conn)

    def upsert_track_maps(self, records: List[TrackMapRecord], conn: Optional[sqlite3.Connection] = None) -> None:
        if not records:
            return

        def _do_work(c: sqlite3.Connection):
            params = [
                (
                    r.guid,
                    s64(r.ipod_dbid),
                    r.local_path,
                    r.local_mtime,
                    r.local_size,
                    r.content_hash,
                    r.ipod_relpath,
                    r.transcoded,
                    r.source_codec,
                    r.synced_at or int(time.time()),
                )
                for r in records
            ]
            c.executemany(
                """
                INSERT INTO track_map (
                    guid, ipod_dbid, local_path, local_mtime, local_size,
                    content_hash, ipod_relpath, transcoded, source_codec, synced_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guid, ipod_dbid) DO UPDATE SET
                    local_path = excluded.local_path,
                    local_mtime = excluded.local_mtime,
                    local_size = excluded.local_size,
                    content_hash = excluded.content_hash,
                    ipod_relpath = excluded.ipod_relpath,
                    transcoded = excluded.transcoded,
                    source_codec = excluded.source_codec,
                    synced_at = excluded.synced_at;
                """,
                params,
            )
            if conn is None:
                c.commit()

        if conn is not None:
            _do_work(conn)
        else:
            with self._connection() as c:
                _do_work(c)

    def get_track_map(self, guid: str, ipod_dbid: int) -> Optional[TrackMapRecord]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM track_map WHERE guid = ? AND ipod_dbid = ?",
                (guid, s64(ipod_dbid)),
            ).fetchone()
            if not row:
                return None
            return self._row_to_track_map(row)

    def get_track_map_by_local_path(self, guid: str, local_path: str) -> Optional[TrackMapRecord]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM track_map WHERE guid = ? AND local_path = ?",
                (guid, local_path),
            ).fetchone()
            if not row:
                return None
            return self._row_to_track_map(row)

    def list_track_maps(self, guid: str) -> List[TrackMapRecord]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM track_map WHERE guid = ? ORDER BY local_path",
                (guid,),
            ).fetchall()
            return [self._row_to_track_map(r) for r in rows]

    def delete_track_maps(self, guid: str, ipod_dbids: List[int], conn: Optional[sqlite3.Connection] = None) -> int:
        if not ipod_dbids:
            return 0

        def _do_work(c: sqlite3.Connection) -> int:
            placeholders = ",".join("?" for _ in ipod_dbids)
            params = [guid] + [s64(d) for d in ipod_dbids]
            cur = c.execute(
                f"DELETE FROM track_map WHERE guid = ? AND ipod_dbid IN ({placeholders})",
                params,
            )
            if conn is None:
                c.commit()
            return cur.rowcount

        if conn is not None:
            return _do_work(conn)
        with self._connection() as c:
            return _do_work(c)

    @staticmethod
    def _row_to_track_map(row: sqlite3.Row) -> TrackMapRecord:
        return TrackMapRecord(
            guid=row["guid"],
            ipod_dbid=u64(row["ipod_dbid"]),
            local_path=row["local_path"],
            local_mtime=row["local_mtime"],
            local_size=row["local_size"],
            content_hash=row["content_hash"],
            ipod_relpath=row["ipod_relpath"],
            transcoded=row["transcoded"],
            source_codec=row["source_codec"],
            synced_at=row["synced_at"],
        )

    # ── Playback State ─────────────────────────────────────────────────────

    def upsert_playback_state(self, rec: PlaybackStateRecord, conn: Optional[sqlite3.Connection] = None) -> None:
        self.upsert_playback_states([rec], conn=conn)

    def upsert_playback_states(self, records: List[PlaybackStateRecord], conn: Optional[sqlite3.Connection] = None) -> None:
        if not records:
            return

        def _do_work(c: sqlite3.Connection):
            params = [
                (
                    r.guid,
                    s64(r.ipod_dbid),
                    r.known_play_count,
                    r.known_rating,
                    r.known_last_played,
                    r.known_skip_count,
                    r.known_date_skipped,
                    r.synced_at or int(time.time()),
                )
                for r in records
            ]
            c.executemany(
                """
                INSERT INTO playback_state (
                    guid, ipod_dbid, known_play_count, known_rating,
                    known_last_played, known_skip_count, known_date_skipped, synced_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guid, ipod_dbid) DO UPDATE SET
                    known_play_count = excluded.known_play_count,
                    known_rating = excluded.known_rating,
                    known_last_played = excluded.known_last_played,
                    known_skip_count = excluded.known_skip_count,
                    known_date_skipped = excluded.known_date_skipped,
                    synced_at = excluded.synced_at;
                """,
                params,
            )
            if conn is None:
                c.commit()

        if conn is not None:
            _do_work(conn)
        else:
            with self._connection() as c:
                _do_work(c)

    def get_playback_state(self, guid: str, ipod_dbid: int) -> Optional[PlaybackStateRecord]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM playback_state WHERE guid = ? AND ipod_dbid = ?",
                (guid, s64(ipod_dbid)),
            ).fetchone()
            if not row:
                return None
            return self._row_to_playback_state(row)

    def get_all_playback_states(self, guid: str) -> Dict[int, PlaybackStateRecord]:
        """Devuelve un mapa {ipod_dbid (uint64): PlaybackStateRecord} de todas las pistas registradas."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM playback_state WHERE guid = ?",
                (guid,),
            ).fetchall()
            return {u64(r["ipod_dbid"]): self._row_to_playback_state(r) for r in rows}

    @staticmethod
    def _row_to_playback_state(row: sqlite3.Row) -> PlaybackStateRecord:
        return PlaybackStateRecord(
            guid=row["guid"],
            ipod_dbid=u64(row["ipod_dbid"]),
            known_play_count=row["known_play_count"],
            known_rating=row["known_rating"],
            known_last_played=row["known_last_played"],
            known_skip_count=row["known_skip_count"],
            known_date_skipped=row["known_date_skipped"],
            synced_at=row["synced_at"],
        )

    # ── Local Playback State (rating asignado desde Cicada) ─────────────────

    def upsert_local_playback_state(
        self, rec: LocalPlaybackStateRecord, conn: Optional[sqlite3.Connection] = None
    ) -> None:
        self.upsert_local_playback_states([rec], conn=conn)

    def upsert_local_playback_states(
        self, records: List[LocalPlaybackStateRecord], conn: Optional[sqlite3.Connection] = None
    ) -> None:
        if not records:
            return

        def _do_work(c: sqlite3.Connection):
            params = [
                (r.guid, s64(r.ipod_dbid), r.local_rating, r.updated_at or int(time.time()))
                for r in records
            ]
            c.executemany(
                """
                INSERT INTO local_playback_state (guid, ipod_dbid, local_rating, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guid, ipod_dbid) DO UPDATE SET
                    local_rating = excluded.local_rating,
                    updated_at = excluded.updated_at;
                """,
                params,
            )
            if conn is None:
                c.commit()

        if conn is not None:
            _do_work(conn)
        else:
            with self._connection() as c:
                _do_work(c)

    def get_local_playback_state(self, guid: str, ipod_dbid: int) -> Optional[LocalPlaybackStateRecord]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM local_playback_state WHERE guid = ? AND ipod_dbid = ?",
                (guid, s64(ipod_dbid)),
            ).fetchone()
            if not row:
                return None
            return self._row_to_local_playback_state(row)

    def get_all_local_playback_states(self, guid: str) -> Dict[int, LocalPlaybackStateRecord]:
        """Devuelve un mapa {ipod_dbid (uint64): LocalPlaybackStateRecord}."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM local_playback_state WHERE guid = ?",
                (guid,),
            ).fetchall()
            return {u64(r["ipod_dbid"]): self._row_to_local_playback_state(r) for r in rows}

    @staticmethod
    def _row_to_local_playback_state(row: sqlite3.Row) -> LocalPlaybackStateRecord:
        return LocalPlaybackStateRecord(
            guid=row["guid"],
            ipod_dbid=u64(row["ipod_dbid"]),
            local_rating=row["local_rating"],
            updated_at=row["updated_at"],
        )

    # ── Playlists Map ──────────────────────────────────────────────────────

    def upsert_playlist_map(self, rec: PlaylistMapRecord, conn: Optional[sqlite3.Connection] = None) -> None:
        def _do_work(c: sqlite3.Connection):
            c.execute(
                """
                INSERT INTO playlists_map (guid, playlist_id, name, is_smart, track_count, synced_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guid, playlist_id) DO UPDATE SET
                    name = excluded.name,
                    is_smart = excluded.is_smart,
                    track_count = excluded.track_count,
                    synced_at = excluded.synced_at;
                """,
                (
                    rec.guid,
                    s64(rec.playlist_id),
                    rec.name,
                    1 if rec.is_smart else 0,
                    rec.track_count,
                    rec.synced_at or int(time.time()),
                ),
            )
            if conn is None:
                c.commit()

        if conn is not None:
            _do_work(conn)
        else:
            with self._connection() as c:
                _do_work(c)

    def list_playlists_map(self, guid: str) -> List[PlaylistMapRecord]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM playlists_map WHERE guid = ? ORDER BY name",
                (guid,),
            ).fetchall()
            return [
                PlaylistMapRecord(
                    guid=r["guid"],
                    playlist_id=u64(r["playlist_id"]),
                    name=r["name"],
                    is_smart=bool(r["is_smart"]),
                    track_count=r["track_count"],
                    synced_at=r["synced_at"],
                )
                for r in rows
            ]

    def delete_playlist_maps(
        self,
        guid: str,
        playlist_ids: Optional[List[int]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        def _do_work(c: sqlite3.Connection) -> int:
            if playlist_ids is None:
                cur = c.execute("DELETE FROM playlists_map WHERE guid = ?", (guid,))
            else:
                placeholders = ",".join("?" for _ in playlist_ids)
                params = [guid] + [s64(p) for p in playlist_ids]
                cur = c.execute(f"DELETE FROM playlists_map WHERE guid = ? AND playlist_id IN ({placeholders})", params)
            if conn is None:
                c.commit()
            return cur.rowcount

        if conn is not None:
            return _do_work(conn)
        with self._connection() as c:
            return _do_work(c)
