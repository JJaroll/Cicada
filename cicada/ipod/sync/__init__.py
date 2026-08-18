"""Módulo de sincronización y estado persistente para iPod — Fase 3."""
from __future__ import annotations

from .bidirectional import (
    PlaybackDeltaReport,
    RawPlaybackStat,
    TrackPlaybackDelta,
    commit_playback_deltas,
    compute_playback_deltas,
    read_ipod_playback_stats,
    sync_playback_stats,
)
from .conflicts import (
    ConflictScanResult,
    PendingLocalPush,
    RatingConflict,
    scan_for_conflicts,
)
from .playlists import (
    LocalPlaylist,
    PreparedPlaylists,
    extract_smart_playlists_for_preservation,
    prepare_all_playlists,
    prepare_standard_playlists,
    record_playlists_in_db,
)
from .state import (
    DeviceRecord,
    LocalPlaybackStateRecord,
    PlaybackStateRecord,
    PlaylistMapRecord,
    SyncStateDB,
    TrackMapRecord,
    default_sync_db_path,
)

__all__ = [
    "ConflictScanResult",
    "DeviceRecord",
    "LocalPlaybackStateRecord",
    "LocalPlaylist",
    "PendingLocalPush",
    "PlaybackDeltaReport",
    "PlaybackStateRecord",
    "PlaylistMapRecord",
    "PreparedPlaylists",
    "RatingConflict",
    "RawPlaybackStat",
    "SyncStateDB",
    "TrackMapRecord",
    "TrackPlaybackDelta",
    "commit_playback_deltas",
    "compute_playback_deltas",
    "default_sync_db_path",
    "extract_smart_playlists_for_preservation",
    "prepare_all_playlists",
    "prepare_standard_playlists",
    "read_ipod_playback_stats",
    "record_playlists_in_db",
    "scan_for_conflicts",
    "sync_playback_stats",
]
