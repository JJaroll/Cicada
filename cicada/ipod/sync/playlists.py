"""Sincronización y preservación de listas de reproducción para iPod — Fase 3.

Responsabilidades:
1. Conversión de listas de reproducción estándar locales a instancias `PlaylistInfo`
   resolviendo los paths locales a `ipod_dbid`s y asignando IDs de 64 bits.
2. Preservación byte-exacta de Smart Playlists existentes en el iPod (v1: sin evaluar,
   re-escribiendo sus blobs de reglas y preferencias `mhod50`, `mhod51`, `mhod55`, `mhod100`, `mhod102`).
3. Actualización del mapeo de playlists en `SyncStateDB`.
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from cicada.ipod.db.parser import load_ipod_library
from cicada.ipod.db.sqlite._helpers import u64
from cicada.ipod.db.writer.mhod_spl_writer import (
    SmartPlaylistPrefs,
    SmartPlaylistRule,
    SmartPlaylistRules,
)
from cicada.ipod.db.writer.mhyp_writer import PlaylistInfo, PlaylistItemMeta
from cicada.ipod.sync.state import PlaylistMapRecord, SyncStateDB

logger = logging.getLogger(__name__)


def _generate_playlist_id() -> int:
    """Genera un identificador positivo de 64 bits para una lista de reproducción."""
    return (int(time.time() * 1000) ^ random.randint(1, 0xFFFFFF)) & 0x7FFFFFFFFFFFFFFF


# ═══════════════════════════════════════════════════════════════════════════
# Dataclasses de Entrada y Resultados
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class LocalPlaylist:
    """Definición de una lista de reproducción estándar proveniente de Cicada."""
    name: str
    track_paths: List[str] = field(default_factory=list)
    playlist_id: Optional[int] = None


@dataclass
class PreparedPlaylists:
    """Conjunto consolidado de playlists listas para pasar a `create_plan()`."""
    standard_playlists: List[PlaylistInfo] = field(default_factory=list)
    smart_playlists: List[PlaylistInfo] = field(default_factory=list)
    unresolved_tracks_count: int = 0

    @property
    def all_playlists(self) -> List[PlaylistInfo]:
        return self.standard_playlists + self.smart_playlists


# ═══════════════════════════════════════════════════════════════════════════
# Conversión de Playlists Estándar
# ═══════════════════════════════════════════════════════════════════════════

def prepare_standard_playlists(
    local_playlists: Sequence[LocalPlaylist],
    guid: str,
    sync_db: Optional[SyncStateDB] = None,
    path_to_dbid_map: Optional[Dict[str, int]] = None,
) -> Tuple[List[PlaylistInfo], int]:
    """Convierte listas de reproducción locales a `PlaylistInfo` resolviendo los dbids de pistas.

    :param local_playlists: Colección de listas locales a sincronizar.
    :param guid: FireWireGUID del iPod.
    :param sync_db: Repositorio persistente `SyncStateDB` (opcional si se provee path_to_dbid_map).
    :param path_to_dbid_map: Mapa directo `{local_path: ipod_dbid}` para resolución en memoria.
    :returns: Tupla `(playlists_info, total_unresolved_tracks)`.
    """
    resolved_playlists: List[PlaylistInfo] = []
    total_unresolved = 0

    # Construir mapa de resolución local_path -> ipod_dbid si contamos con sync_db
    local_map: Dict[str, int] = {}
    if path_to_dbid_map:
        local_map.update(path_to_dbid_map)
    elif sync_db:
        for t in sync_db.list_track_maps(guid):
            local_map[t.local_path] = t.ipod_dbid

    for lp in local_playlists:
        track_ids: List[int] = []
        for p in lp.track_paths:
            dbid = local_map.get(p)
            if dbid is not None:
                track_ids.append(u64(dbid))
            else:
                total_unresolved += 1
                logger.warning("Pista en playlist %r no encontrada en track_map: %s", lp.name, p)

        # Garantizar que siempre tenga un playlist_id de 64 bits
        pl_id = u64(lp.playlist_id) if lp.playlist_id is not None else _generate_playlist_id()

        pl_info = PlaylistInfo(
            name=lp.name,
            track_ids=track_ids,
            playlist_id=pl_id,
            master=False,
        )
        resolved_playlists.append(pl_info)

    return resolved_playlists, total_unresolved


# ═══════════════════════════════════════════════════════════════════════════
# Preservación de Smart Playlists (v1)
# ═══════════════════════════════════════════════════════════════════════════

def extract_smart_playlists_for_preservation(mount: Path | str) -> List[PlaylistInfo]:
    """Extrae las smart playlists existentes en el iPod preservando sus blobs crudos.

    Lee `iTunesCDB` o `iTunesDB` con el parser y rescata las reglas y configuraciones
    `smart_prefs`, `smart_rules`, `raw_mhod55`, `raw_mhod100`, `raw_mhod102` y metadatos de MHIP.
    """
    mount_path = Path(mount)
    itunes_dir = mount_path / "iPod_Control" / "iTunes"
    cdb_file = itunes_dir / "iTunesCDB"
    db_file = itunes_dir / "iTunesDB"
    target_file = cdb_file if cdb_file.is_file() else db_file

    if not target_file.is_file():
        return []

    lib = load_ipod_library(str(target_file), merge_playcounts=False, mount=str(mount_path))
    if not lib:
        return []

    # En load_ipod_library, las playlists se organizan en mhlp_smart, mhlp, mhlp_podcast o mhyp
    raw_playlists = (
        lib.get("mhlp_smart", [])
        + lib.get("mhlp", [])
        + lib.get("mhlp_podcast", [])
        + lib.get("mhyp", [])
    )
    smart_playlists: List[PlaylistInfo] = []

    for pl in raw_playlists:
        is_smart = bool(
            pl.get("is_smart")
            or pl.get("smart_playlist_data")
            or pl.get("smart_playlist_rules")
            or pl.get("smart_prefs")
            or pl.get("smart_rules")
        )
        if not is_smart:
            continue

        name = pl.get("name") or pl.get("Title") or "Smart Playlist"
        playlist_id_raw = pl.get("playlist_id") or pl.get("id")
        playlist_id = u64(playlist_id_raw) if playlist_id_raw is not None else _generate_playlist_id()

        # Extraer / convertir smart_prefs
        smart_prefs = pl.get("smart_prefs")
        if smart_prefs is None and pl.get("smart_playlist_data"):
            d = pl.get("smart_playlist_data")
            if isinstance(d, dict):
                smart_prefs = SmartPlaylistPrefs(
                    live_update=bool(d.get("live_update", 1)),
                    check_rules=bool(d.get("check_rules", 1)),
                    check_limits=bool(d.get("check_limits", 0)),
                    limit_type=d.get("limit_type", 3),
                    limit_sort=d.get("limit_sort", 2),
                    limit_value=d.get("limit_value", 25),
                    match_checked_only=bool(d.get("match_checked_only", 0)),
                )
            elif isinstance(d, SmartPlaylistPrefs):
                smart_prefs = d

        # Extraer / convertir smart_rules
        smart_rules = pl.get("smart_rules")
        if smart_rules is None and pl.get("smart_playlist_rules"):
            r = pl.get("smart_playlist_rules")
            if isinstance(r, dict):
                rules_list: List[SmartPlaylistRule] = []
                for raw_r in r.get("rules", []):
                    rules_list.append(
                        SmartPlaylistRule(
                            field_id=raw_r.get("field_id", 0x02),
                            action_id=raw_r.get("action_id", 0x01000002),
                            string_value=raw_r.get("string_value"),
                            from_value=raw_r.get("from_value", 0),
                            from_date=raw_r.get("from_date", 0),
                            from_units=raw_r.get("from_units", 0),
                            to_value=raw_r.get("to_value", 0),
                            to_date=raw_r.get("to_date", 0),
                            to_units=raw_r.get("to_units", 0),
                            unk052=raw_r.get("unk052", 0),
                            unk056=raw_r.get("unk056", 0),
                            unk060=raw_r.get("unk060", 0),
                            unk064=raw_r.get("unk064", 0),
                            unk068=raw_r.get("unk068", 0),
                        )
                    )
                smart_rules = SmartPlaylistRules(
                    conjunction="OR" if r.get("conjunction") == 1 else "AND",
                    rules=rules_list,
                    unk004=r.get("unk004", 0),
                )
            elif isinstance(r, SmartPlaylistRules):
                smart_rules = r

        raw_mhod55 = pl.get("raw_mhod55")
        raw_mhod100 = pl.get("raw_mhod100")
        raw_mhod102 = pl.get("raw_mhod102")
        mhsd5_type = pl.get("mhsd5_type") or 0
        podcast_flag = pl.get("podcast_flag") or 0
        phase_game_flag = pl.get("phase_game_flag") or 0
        sortorder = pl.get("sortorder") or 0

        # Extracción tolerante de track_ids (soporte para track_ids o items / mhip)
        raw_track_ids = pl.get("track_ids")
        if raw_track_ids is None:
            raw_track_ids = [
                m.get("db_track_id")
                or m.get("track_id")
                or m.get("id")
                or m.get("track_persistent_id")
                for m in (pl.get("items", []) or pl.get("mhip", []))
            ]
        track_ids = [u64(t) for t in raw_track_ids if t is not None]

        smart_info = PlaylistInfo(
            name=name,
            track_ids=track_ids,
            playlist_id=playlist_id,
            master=False,
            sortorder=sortorder,
            podcast_flag=podcast_flag,
            smart_prefs=smart_prefs,
            smart_rules=smart_rules,
            mhsd5_type=mhsd5_type,
            phase_game_flag=phase_game_flag,
            raw_mhod55=raw_mhod55,
            raw_mhod100=raw_mhod100,
            raw_mhod102=raw_mhod102,
        )
        smart_playlists.append(smart_info)

    return smart_playlists


# ═══════════════════════════════════════════════════════════════════════════
# Orquestador Unificado
# ═══════════════════════════════════════════════════════════════════════════

def prepare_all_playlists(
    mount: Path | str,
    guid: str,
    local_playlists: Sequence[LocalPlaylist] = (),
    sync_db: Optional[SyncStateDB] = None,
    path_to_dbid_map: Optional[Dict[str, int]] = None,
    preserve_smart_playlists: bool = True,
) -> PreparedPlaylists:
    """Prepara tanto las playlists estándar como las smart playlists para `create_plan()`."""
    std_pls, unresolved = prepare_standard_playlists(
        local_playlists=local_playlists,
        guid=guid,
        sync_db=sync_db,
        path_to_dbid_map=path_to_dbid_map,
    )

    smart_pls: List[PlaylistInfo] = []
    if preserve_smart_playlists:
        smart_pls = extract_smart_playlists_for_preservation(mount)

    return PreparedPlaylists(
        standard_playlists=std_pls,
        smart_playlists=smart_pls,
        unresolved_tracks_count=unresolved,
    )


def record_playlists_in_db(
    guid: str,
    playlists: Sequence[PlaylistInfo],
    sync_db: SyncStateDB,
) -> None:
    """Registra las playlists sincronizadas en `playlists_map` de `SyncStateDB`."""
    now = int(time.time())
    with sync_db.transaction() as conn:
        sync_db.delete_playlist_maps(guid, conn=conn)
        for pl in playlists:
            if pl.playlist_id is not None:
                sync_db.upsert_playlist_map(
                    PlaylistMapRecord(
                        guid=guid,
                        playlist_id=pl.playlist_id,
                        name=pl.name,
                        is_smart=pl.is_smart,
                        track_count=len(pl.track_ids),
                        synced_at=now,
                    ),
                    conn=conn,
                )
