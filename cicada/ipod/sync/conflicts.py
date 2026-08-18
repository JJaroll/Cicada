"""Detección de conflictos de rating — Fase 3 (resolución de conflictos).

Diff de tres vías (local / dispositivo / baseline) para el único campo
sincronizable que no se puede fusionar automáticamente: el rating. Los
contadores (play_count/skip_count) se suman y los timestamps toman ``max()``
en bidirectional.py — no son conflictivos y no pasan por aquí.

Política: nunca resolver un conflicto real en silencio. Este módulo solo
clasifica y reporta; no escribe nada (ni en SQLite local ni en el iPod).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from cicada.ipod.sync.bidirectional import read_ipod_playback_stats
from cicada.ipod.sync.state import SyncStateDB


@dataclass
class RatingConflict:
    """Ambos lados cambiaron desde el último sync Y difieren entre sí —
    ninguno de los dos valores es automáticamente correcto."""
    guid: str
    ipod_dbid: int
    local_path: Optional[str]
    known_rating: int    # baseline del último sync
    local_rating: int    # local_playback_state actual
    device_rating: int   # lectura en vivo del iPod


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
            continue  # el lado local no cambió: nada que evaluar

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
            # device_rating == known_rating (solo local cambió) o
            # device_rating == local.local_rating (ambos llegaron al mismo
            # valor): en ambos casos no hay desacuerdo que resolver.
            result.pending_local_pushes.append(PendingLocalPush(
                guid=guid, ipod_dbid=dbid, local_path=local_path,
                known_rating=known.known_rating, local_rating=local.local_rating,
            ))

    return result
