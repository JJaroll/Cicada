"""DTOs de entrada de escritura del iTunesDB: TrackInfo, PlaylistInfo y su
PlaylistItemMeta. Antes vivían dentro de los módulos-chunk del writer
(mhit_writer/mhyp_writer), lo que forzaba a sqlite/coordinator/api a importar de
las tripas del writer; aquí quedan como tipos neutrales compartidos."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cicada.ipod.db.shared.constants import MEDIA_TYPE_AUDIO

if TYPE_CHECKING:
    from cicada.ipod.db.writer.mhod_spl_writer import (
        SmartPlaylistPrefs,
        SmartPlaylistRules,
    )


@dataclass
class TrackInfo:
    """Track metadata for writing to iTunesDB."""

    # Required
    title: str
    location: str  # iPod path like ":iPod_Control:Music:F00:ABCD.mp3"

    # File info
    size: int = 0  # File size in bytes
    length: int = 0  # Duration in milliseconds
    filetype: str = 'mp3'  # mp3, m4a, m4p, etc.
    bitrate: int = 0  # kbps
    sample_rate: int = 44100  # Hz
    vbr: bool = False

    # Metadata
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    genre: str | None = None
    composer: str | None = None
    comment: str | None = None
    year: int = 0
    track_number: int = 0
    total_tracks: int = 0
    disc_number: int = 1
    total_discs: int = 1
    bpm: int = 0
    compilation_flag: bool = False

    # Playback
    rating: int = 0  # 0-100 (stars × 20)
    play_count: int = 0
    play_count_2: int = 0
    skip_count: int = 0
    volume: int = 0  # -255 to +255
    start_time: int = 0  # ms
    stop_time: int = 0  # ms
    sound_check: int = 0  # Volume normalization value (from ReplayGain)
    bookmark_time: int = 0  # Resume position in ms (audiobooks/podcasts)
    checked_flag: int = 0  # 0 = checked/enabled, 1 = unchecked/disabled

    # Gapless playback
    gapless_data: int = 0  # Gapless playback encoder delay data
    gapless_track_flag: int = 0  # 1 = track has gapless info
    gapless_album_flag: int = 0  # 1 = album is gapless
    pregap: int = 0  # Encoder pregap samples
    postgap: int = 0  # Encoder postgap/padding samples (0xC8)
    sample_count: int = 0  # Total decoded sample count (64-bit)
    encoder_flag: int = 0  # 0xCC: 0x01=MP3 encoder, 0x00=other

    # Track flags
    skip_when_shuffling: bool = False  # 1 = skip in shuffle mode
    remember_position: bool = False    # 1 = resume from bookmark (audiobooks)
    podcast_flag: int = 0  # 0xA7: 0x00=normal, 0x01/0x02=podcast
    movie_file_flag: int = 0  # 0xB1: 0x01=video/movie file, 0x00=audio
    played_mark: int = -1  # 0xB2: -1=auto (derive from play_count), 0x01=played, 0x02=unplayed
    explicit_flag: int = 0  # 0=none, 1=explicit, 2=clean
    purchased_aac_flag: int = 0  # 0x93: 1 for M4A/iTunes purchases, 0 for most MP3s
    has_lyrics: bool = False  # True if track has embedded lyrics
    lyrics: str | None = None  # Full lyrics text (MHOD type 10)
    eq_setting: str | None = None  # EQ preset name (MHOD type 7), e.g. "Bass Booster"

    # Timestamps (Unix)
    date_added: int = 0  # Will be set to now if 0
    date_released: int = 0
    last_modified: int = 0  # 0x20: file modification time (0 = use date_added)
    last_played: int = 0
    last_skipped: int = 0

    # iPod-specific
    track_id: int = 0  # Will be assigned during write
    db_track_id: int = 0  # Will be generated if 0
    media_type: int = MEDIA_TYPE_AUDIO
    season_number: int = 0  # 0xD4: TV show season number
    episode_number: int = 0  # 0xD8: TV show episode number
    artwork_count: int = 0
    artwork_size: int = 0
    mhii_link: int = 0  # Link to ArtworkDB
    album_id: int = 0  # Links to MHIA album entry
    source_path: str | None = None  # PC source path; internal write-time helper context
    source_relative_path: str | None = None  # PC path relative to library root, if known

    # Sorting
    sort_artist: str | None = None
    sort_name: str | None = None
    sort_album: str | None = None
    sort_album_artist: str | None = None
    sort_composer: str | None = None

    # Extra string metadata
    grouping: str | None = None
    keywords: str | None = None  # MHOD type 24 (track keywords)

    # Podcast string metadata (written as MHODs)
    podcast_enclosure_url: str | None = None  # MHOD type 15
    podcast_rss_url: str | None = None        # MHOD type 16
    category: str | None = None               # MHOD type 9

    # Video string metadata (written as MHODs)
    description: str | None = None       # MHOD type 14
    subtitle: str | None = None          # MHOD type 18
    show_name: str | None = None         # MHOD type 19 (TV show name)
    episode_id: str | None = None        # MHOD type 20 (e.g. "S01E05")
    network_name: str | None = None      # MHOD type 21 (TV network)
    sort_show: str | None = None         # MHOD type 31
    show_locale: str | None = None       # MHOD type 25 (show locale, e.g. "en_US")

    # Filetype description
    filetype_desc: str | None = None  # e.g., "MPEG audio file"

    # Round-trip fields (preserved from existing iPod database)
    user_id: int = 0      # 0x64: DRM user ID (preserved for round-trip)
    app_rating: int = 0   # 0x79: Application-computed rating (preserved for round-trip)
    mpeg_audio_type: int = 0  # 0x90: MPEG Audio Object Type (12=MP3, 51=AAC, 41=Audible)

    # iTunes Store metadata (round-trip, only for Store purchases)
    date_added_to_itunes: int = 0    # 0xDC: Unix ts, original iTunes library add date
    store_track_id: int = 0          # 0xE0: iTunes Store per-track content ID
    store_encoder_version: int = 0   # 0xE4: iTunes version that encoded the file
    store_artist_id: int = 0         # 0xE8: iTunes Store artist/collection ID
    store_album_id: int = 0          # 0xF0: iTunes Store album ID
    store_content_flag: int = 0      # 0xF4: iTunes Store content type flag

    # Internal IDs (assigned during database write, NOT user-provided)
    artist_id: int = 0   # Links to artist entry (assigned by writer)
    composer_id: int = 0  # Links to composer entry (assigned by writer)

    # Chapter data (MHOD type 17) lives in iTunesDB, independent of filetype.
    chapter_data: dict | None = None

    # Internal sync hint (transient, not written to database)
    # Used by ArtworkDB writer to determine preservation strategy:
    # "preserve_existing" = use existing art without re-encoding
    # "clear_art" = remove art for this track
    # "" (empty) = normal processing
    _iop_artwork_sync_hint: str = ""

    @property
    def db_id(self) -> int:
        """Backward-compatible alias for the track persistent ID."""
        return self.db_track_id

    @db_id.setter
    def db_id(self, value: int) -> None:
        self.db_track_id = value


@dataclass
class PlaylistItemMeta:
    """Per-item metadata preserved from parsed MHIP entries for round-trip fidelity.

    These fields map directly to MHIP header offsets:
      +0x10: podcast_group_flag (4B)
      +0x14: group_id (4B) — unique MHIP identifier (libgpod: podcastgroupid)
      +0x20: podcast_group_ref (4B) — references another MHIP's group_id
      +0x2C: track_persistent_id (8B) — track's db_track_id
      +0x3C: mhip_persistent_id (8B) — per-track persistent ID
    """
    podcast_group_flag: int = 0
    group_id: int = 0
    podcast_group_ref: int = 0
    track_persistent_id: int = 0
    mhip_persistent_id: int = 0


@dataclass
class PlaylistInfo:
    """Structured input for writing a playlist to iTunesDB.

    Covers regular playlists, smart playlists, and the master playlist.
    The master playlist is constructed internally by write_master_playlist()
    and does not need a PlaylistInfo.
    """
    name: str
    track_ids: list[int] = field(default_factory=list)

    # Identity
    playlist_id: int | None = None   # 64-bit; generated if None
    master: bool = False                 # Sets type byte at +0x14 to 1.
    #   Dataset 2: True for the master playlist only (exactly one).
    #   Dataset 5: sample-dependent category marker; preserve parsed input.
    #   In both cases this controls: (a) the type byte at +0x14,
    #   (b) whether library indices are generated (only when tracks
    #       are also provided), and (c) whether db_id_2/playlist_id
    #       are written at the extended offsets +0x3C/+0x44 (skipped
    #       when master=True, matching libgpod behaviour).
    sortorder: int = 0                   # 0=default, 1=manual, 3=title ...
    podcast_flag: int = 0                # 0x2A: 0=normal, 1=podcast playlist (u16)

    # Smart playlist fields (both must be set for a smart playlist)
    smart_prefs: SmartPlaylistPrefs | None = None
    smart_rules: SmartPlaylistRules | None = None

    # mhsd5Type: browsing category for dataset 5 smart playlists
    # (per libgpod: 0=None, 2=Movies, 3=TV Shows, 4=Music, 5=Audiobooks, 6=Ringtones, 7=MovieRentals)
    mhsd5_type: int = 0

    # Exact raw u16 at MHYP +0x52. Observed as 25 (0x0019) on iTunes-created
    # Phase Music playlists; its precise firmware meaning is not yet proven.
    phase_game_flag: int = 0

    # Opaque blobs preserved from parsed data for round-trip fidelity
    raw_mhod100: bytes | None = None   # Playlist prefs (type 100 body)
    raw_mhod102: bytes | None = None   # Playlist settings (type 102 body)
    raw_mhod55: bytes | None = None    # Playlist property plist (type 55 body)
    playlist_description: str | None = None

    # Per-MHIP metadata preserved from parsed data for round-trip fidelity.
    # When provided, must be the same length as track_ids and in the same order.
    item_metadata: list[PlaylistItemMeta] | None = None

    @property
    def is_smart(self) -> bool:
        return self.smart_prefs is not None and self.smart_rules is not None
