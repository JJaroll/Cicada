"""Detección y resolución de conflictos de rating — Fase 3.

Diff de tres vías (local / dispositivo / baseline) para el único campo
sincronizable que no se puede fusionar automáticamente: el rating. Los
contadores (play_count/skip_count) se suman y los timestamps toman ``max()``
en bidirectional.py — no son conflictivos y no pasan por aquí.

Política: nunca resolver un conflicto real en silencio. ``scan_for_conflicts``
solo clasifica (no escribe nada); ``resolve_conflicts`` requiere que el
llamador indique explícitamente qué lado gana — nunca decide por su cuenta.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from cicada.ipod.db.coordinator.apply import ApplyResult
from cicada.ipod.sync.bidirectional import read_ipod_playback_stats
from cicada.ipod.sync.state import LocalPlaybackStateRecord, PlaybackStateRecord, SyncStateDB


@dataclass
class RatingConflict:
    """Ambos lados cambiaron desde el último sync Y difieren entre sí —
    ninguno de los dos valores es automáticamente correcto."""
    guid: str
    ipod_dbid: int
    local_path: Optional[str]
    known_rating: int
    local_rating: int
    device_rating: int


@dataclass
class PendingLocalPush:
    """Solo el lado local cambió (o ambos cambiaron al mismo valor): no es
    conflicto — falta empujar el rating local al dispositivo."""
    guid: str
    ipod_dbid: int
    local_path: Optional[str]
    known_rating: int
    local_rating: int


@dataclass
class ConflictScanResult:
    guid: str
    conflicts: List[RatingConflict] = field(default_factory=list)
    pending_local_pushes: List[PendingLocalPush] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0


def scan_for_conflicts(mount: Path | str, sync_db: SyncStateDB, guid: str) -> ConflictScanResult:
    """Clasifica cada pista cuyo rating local se apartó del baseline.

    Pistas sin baseline (``known is None``) se ignoran: sin un último sync
    conocido no hay "cambio desde entonces" que evaluar — bidirectional.py ya
    las trata como primera aparición, no como conflicto.
    """
    known_states = sync_db.get_all_playback_states(guid)
    local_states = sync_db.get_all_local_playback_states(guid)
    device_stats = read_ipod_playback_stats(mount)

    result = ConflictScanResult(guid=guid)

    for dbid, local in local_states.items():
        known = known_states.get(dbid)
        if known is None:
            continue
        if local.local_rating == known.known_rating:
            continue

        stat = device_stats.get(dbid)
        device_rating = stat.rating if stat is not None else known.known_rating

        tmap = sync_db.get_track_map(guid, dbid)
        local_path = tmap.local_path if tmap else None

        if device_rating != known.known_rating and device_rating != local.local_rating:
            result.conflicts.append(RatingConflict(
                guid=guid, ipod_dbid=dbid, local_path=local_path,
                known_rating=known.known_rating, local_rating=local.local_rating,
                device_rating=device_rating,
            ))
        else:
            result.pending_local_pushes.append(PendingLocalPush(
                guid=guid, ipod_dbid=dbid, local_path=local_path,
                known_rating=known.known_rating, local_rating=local.local_rating,
            ))

    return result


def resolve_conflicts(
    mount: Path | str,
    sync_db: SyncStateDB,
    conflicts: List[RatingConflict],
    resolution: str,
    *,
    device_info,
    consent_ack: bool = False,
) -> ApplyResult:
    """Aplica ``resolution`` ("local" | "device") a uno o más conflictos ya
    detectados, en un solo lote. "local": escribe los ratings locales al
    iPod (un único ``apply()``, no uno por pista) y luego alinea ambas
    tablas locales al valor ganador. "device": no escribe nada en el iPod
    (ya tiene ese valor) — solo alinea las tablas locales. En ambos casos,
    ``playback_state`` y ``local_playback_state`` quedan consistentes entre
    sí al terminar (mismo valor de rating en las dos), para que el próximo
    escaneo no vuelva a marcar el mismo conflicto.
    """
    if resolution not in ("local", "device"):
        raise ValueError(f"resolution inválida: {resolution!r} (debe ser 'local' o 'device')")
    if not conflicts:
        return ApplyResult(success=True, tracks_written=0)

    guid = conflicts[0].guid
    winning: Dict[int, int] = {}
    result: Optional[ApplyResult] = None

    if resolution == "local":
        from cicada.ipod.db.coordinator.media import push_ratings_to_ipod
        ratings = {c.ipod_dbid: c.local_rating for c in conflicts}
        result = push_ratings_to_ipod(mount, ratings, device_info=device_info, consent_ack=consent_ack)
        if not result.success:
            return result
        winning = ratings
    else:
        winning = {c.ipod_dbid: c.device_rating for c in conflicts}

    now = int(time.time())
    with sync_db.transaction() as conn:
        for c in conflicts:
            known = sync_db.get_playback_state(guid, c.ipod_dbid)
            rating = winning[c.ipod_dbid]
            sync_db.upsert_playback_state(PlaybackStateRecord(
                guid=guid, ipod_dbid=c.ipod_dbid,
                known_play_count=known.known_play_count if known else 0,
                known_rating=rating,
                known_last_played=known.known_last_played if known else 0,
                known_skip_count=known.known_skip_count if known else 0,
                known_date_skipped=known.known_date_skipped if known else 0,
                synced_at=now,
            ), conn=conn)
            sync_db.upsert_local_playback_state(LocalPlaybackStateRecord(
                guid=guid, ipod_dbid=c.ipod_dbid, local_rating=rating, updated_at=now,
            ), conn=conn)

    return result if result is not None else ApplyResult(success=True, tracks_written=len(conflicts))
