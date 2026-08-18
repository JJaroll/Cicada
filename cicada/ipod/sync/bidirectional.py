"""Motor de sincronización bidireccional de reproducciones del iPod — Fase 3.

Lee contadores de reproducción, calificaciones y timestamps desde el iPod
(Dynamic.itdb en Nano 6G/7G o iTunesDB/iTunesCDB en clásicos), los normaliza a
época Unix (1970) y calcula los deltas frente al baseline persistido en SyncStateDB.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from cicada.ipod.db.parser import load_ipod_library
from cicada.ipod.db.shared.device_time import read_device_time_context
from cicada.ipod.db.sqlite._helpers import coredata_to_unix, u64
from cicada.ipod.sync.state import DeviceRecord, PlaybackStateRecord, SyncStateDB

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Dataclasses de Resultados y Deltas
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class RawPlaybackStat:
    """Valores absolutos leídos directamente del iPod (normalizados a Unix epoch)."""
    ipod_dbid: int  # uint64
    play_count: int = 0
    rating: int = 0  # 0..100
    last_played: int = 0  # Unix timestamp 1970
    skip_count: int = 0
    date_skipped: int = 0  # Unix timestamp 1970


@dataclass
class TrackPlaybackDelta:
    """Deltas calculados para una pista individual."""
    guid: str
    ipod_dbid: int  # uint64
    local_path: Optional[str] = None
    delta_play_count: int = 0
    current_play_count: int = 0
    rating_changed: bool = False
    new_rating: int = 0  # 0..100
    new_stars: int = 0   # 0..5
    new_last_played: int = 0  # Unix timestamp 1970
    delta_skip_count: int = 0
    current_skip_count: int = 0
    new_date_skipped: int = 0  # Unix timestamp 1970


@dataclass
class PlaybackDeltaReport:
    """Informe consolidado de cambios de reproducción pendientes de sincronizar."""
    guid: str
    total_tracks_scanned: int = 0
    tracks_with_deltas: List[TrackPlaybackDelta] = field(default_factory=list)
    total_delta_plays: int = 0
    total_delta_skips: int = 0
    ratings_updated_count: int = 0
    scanned_at: int = field(default_factory=lambda: int(time.time()))

    @property
    def has_changes(self) -> bool:
        return len(self.tracks_with_deltas) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Lector de Estadísticas del iPod
# ═══════════════════════════════════════════════════════════════════════════

def read_ipod_playback_stats(mount: Path | str) -> Dict[int, RawPlaybackStat]:
    """Lee y normaliza las estadísticas de reproducción actuales del iPod.

    Prioriza `Dynamic.itdb` (Nano 6G/7G) y realiza fallback a `iTunesCDB`/`iTunesDB`.
    Devuelve un diccionario `{ipod_dbid (uint64): RawPlaybackStat}`.
    """
    mount_path = Path(mount)
    dynamic_itdb = mount_path / "iPod_Control" / "iTunes" / "iTunes Library.itlp" / "Dynamic.itdb"

    # 1. Vía SQLite (Nano 6G / 7G)
    if dynamic_itdb.is_file():
        return _read_stats_from_dynamic_itdb(dynamic_itdb)

    # 2. Vía iTunesCDB / iTunesDB parser (Clásicos / Fallback)
    itunes_dir = mount_path / "iPod_Control" / "iTunes"
    cdb_file = itunes_dir / "iTunesCDB"
    db_file = itunes_dir / "iTunesDB"
    target_file = cdb_file if cdb_file.is_file() else db_file

    if target_file.is_file():
        return _read_stats_from_itunesdb(target_file, mount_path)

    return {}


def _read_stats_from_dynamic_itdb(db_path: Path) -> Dict[int, RawPlaybackStat]:
    stats: Dict[int, RawPlaybackStat] = {}
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            """
            SELECT item_pid, play_count_user, play_count_recent, user_rating,
                   date_played, skip_count_user, skip_count_recent, date_skipped
            FROM item_stats;
            """
        )
        for row in cur:
            dbid = u64(row["item_pid"])
            total_plays = int(row["play_count_user"] or 0) + int(row["play_count_recent"] or 0)
            total_skips = int(row["skip_count_user"] or 0) + int(row["skip_count_recent"] or 0)
            rating = int(row["user_rating"] or 0)

            # Conversión de época Cocoa (2001) a Unix (1970)
            raw_played = row["date_played"] or 0
            last_played = coredata_to_unix(raw_played) if raw_played != 0 else 0

            raw_skipped = row["date_skipped"] or 0
            date_skipped = coredata_to_unix(raw_skipped) if raw_skipped != 0 else 0

            stats[dbid] = RawPlaybackStat(
                ipod_dbid=dbid,
                play_count=total_plays,
                rating=rating,
                last_played=last_played,
                skip_count=total_skips,
                date_skipped=date_skipped,
            )
    finally:
        conn.close()
    return stats


def _read_stats_from_itunesdb(db_file: Path, mount: Path) -> Dict[int, RawPlaybackStat]:
    stats: Dict[int, RawPlaybackStat] = {}
    lib = load_ipod_library(str(db_file), merge_playcounts=True, mount=str(mount))
    if not lib:
        return stats

    time_ctx = read_device_time_context(mount)

    for t in lib.get("mhlt", []):
        dbid_raw = t.get("db_track_id") or t.get("dbid") or 0
        if not dbid_raw:
            continue
        dbid = u64(dbid_raw)
        play_count = int(t.get("play_count") or 0)
        rating = int(t.get("rating") or 0)

        # Conversión de época Mac (1904) a Unix (1970)
        raw_played = int(t.get("last_played") or 0)
        last_played = time_ctx.mac_to_unix(raw_played) if raw_played != 0 else 0

        skip_count = int(t.get("skip_count") or 0)
        raw_skipped = int(t.get("last_skipped") or 0)
        date_skipped = time_ctx.mac_to_unix(raw_skipped) if raw_skipped != 0 else 0

        stats[dbid] = RawPlaybackStat(
            ipod_dbid=dbid,
            play_count=play_count,
            rating=rating,
            last_played=last_played,
            skip_count=skip_count,
            date_skipped=date_skipped,
        )
    return stats


# ═══════════════════════════════════════════════════════════════════════════
# Algoritmo de Cálculo de Deltas
# ═══════════════════════════════════════════════════════════════════════════

def compute_playback_deltas(
    mount: Path | str,
    sync_db: SyncStateDB,
    guid: str,
) -> PlaybackDeltaReport:
    """Calcula los deltas entre el estado actual del iPod y el baseline de SyncStateDB.

    El rating es el único campo no fusionable (play_count/skip_count se suman,
    los timestamps toman ``max()``): si el lado local (``local_playback_state``)
    también se apartó del baseline, este función **no** commitea el rating del
    dispositivo — lo deja tal cual para que ``conflicts.scan_for_conflicts``
    decida. Sin este guard, un conflicto real quedaría resuelto en silencio a
    favor del dispositivo en cada escaneo automático.
    """
    ipod_stats = read_ipod_playback_stats(mount)
    known_states = sync_db.get_all_playback_states(guid)
    local_states = sync_db.get_all_local_playback_states(guid)

    report = PlaybackDeltaReport(guid=guid, total_tracks_scanned=len(ipod_stats))

    for dbid, stat in ipod_stats.items():
        known = known_states.get(dbid)
        delta_play = 0
        delta_skip = 0
        rating_changed = False
        counter_reset = False
        new_last_played = stat.last_played
        new_date_skipped = stat.date_skipped
        committed_rating = stat.rating

        if known is None:
            # Pista no registrada previamente: sin baseline no hay "cambio desde
            # el último sync" que evaluar, así que no puede haber conflicto.
            if stat.play_count > 0:
                delta_play = stat.play_count
            if stat.skip_count > 0:
                delta_skip = stat.skip_count
            if stat.rating > 0:
                rating_changed = True
        else:
            # Pista con línea base conocida
            if stat.play_count > known.known_play_count:
                delta_play = stat.play_count - known.known_play_count
            elif stat.play_count < known.known_play_count:
                # Reinicio o restore en el iPod: no generamos delta negativo pero registramos reset
                delta_play = 0
                counter_reset = True

            if stat.skip_count > known.known_skip_count:
                delta_skip = stat.skip_count - known.known_skip_count
            elif stat.skip_count < known.known_skip_count:
                delta_skip = 0
                counter_reset = True

            local = local_states.get(dbid)
            local_diverged = local is not None and local.local_rating != known.known_rating
            if stat.rating != known.known_rating:
                if local_diverged:
                    # Posible conflicto real (ambos lados cambiaron): no tocar
                    # el baseline aquí, queda pendiente para scan_for_conflicts.
                    committed_rating = known.known_rating
                else:
                    rating_changed = True
            else:
                committed_rating = known.known_rating

            # Timestamp de reproducción más reciente
            new_last_played = max(stat.last_played, known.known_last_played)
            new_date_skipped = max(stat.date_skipped, known.known_date_skipped)

        has_change = (
            delta_play > 0
            or delta_skip > 0
            or rating_changed
            or counter_reset
            or (known is not None and stat.last_played > known.known_last_played)
        )

        if has_change:
            tmap = sync_db.get_track_map(guid, dbid)
            local_path = tmap.local_path if tmap else None

            delta_obj = TrackPlaybackDelta(
                guid=guid,
                ipod_dbid=dbid,
                local_path=local_path,
                delta_play_count=delta_play,
                current_play_count=stat.play_count,
                rating_changed=rating_changed,
                new_rating=committed_rating,
                new_stars=max(0, min(5, committed_rating // 20)),
                new_last_played=new_last_played,
                delta_skip_count=delta_skip,
                current_skip_count=stat.skip_count,
                new_date_skipped=new_date_skipped,
            )
            report.tracks_with_deltas.append(delta_obj)
            report.total_delta_plays += delta_play
            report.total_delta_skips += delta_skip
            if rating_changed:
                report.ratings_updated_count += 1

    return report


def commit_playback_deltas(
    report: PlaybackDeltaReport,
    sync_db: SyncStateDB,
) -> None:
    """Actualiza la línea base en SyncStateDB tras aplicar los deltas con éxito."""
    if not report.has_changes:
        return

    now = int(time.time())
    new_records: List[PlaybackStateRecord] = []

    for item in report.tracks_with_deltas:
        new_records.append(
            PlaybackStateRecord(
                guid=report.guid,
                ipod_dbid=item.ipod_dbid,
                known_play_count=item.current_play_count,
                known_rating=item.new_rating,
                known_last_played=item.new_last_played,
                known_skip_count=item.current_skip_count,
                known_date_skipped=item.new_date_skipped,
                synced_at=now,
            )
        )

    with sync_db.transaction() as conn:
        sync_db.upsert_playback_states(new_records, conn=conn)


# ═══════════════════════════════════════════════════════════════════════════
# Orquestación — punto de entrada único para API/CLI
# ═══════════════════════════════════════════════════════════════════════════

def sync_playback_stats(mount, device_info, sync_db: Optional[SyncStateDB] = None) -> PlaybackDeltaReport:
    """Escanea + confirma en un solo paso: registra el dispositivo (si hace
    falta, por la FK de ``playback_state``), calcula los deltas y los
    persiste como nueva línea base. Punto de entrada único para que API y CLI
    no dupliquen la secuencia ``upsert_device -> compute -> commit``.
    """
    db = sync_db or SyncStateDB()
    db.upsert_device(DeviceRecord(
        guid=device_info.firewire_guid,
        family_id=device_info.family_id,
        model_num=device_info.model_number,
        serial=device_info.serial,
        name=f"{device_info.family or ''} {device_info.generation or ''}".strip() or None,
    ))
    report = compute_playback_deltas(mount, db, device_info.firewire_guid)
    commit_playback_deltas(report, db)
    return report
