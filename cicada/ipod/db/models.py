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

    title: str
    location: str

    size: int = 0
    length: int = 0
    filetype: str = 'mp3'
    bitrate: int = 0
    sample_rate: int = 44100
    vbr: bool = False

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

    rating: int = 0
    play_count: int = 0
    play_count_2: int = 0
    skip_count: int = 0
    volume: int = 0
    start_time: int = 0
    stop_time: int = 0
    sound_check: int = 0
    bookmark_time: int = 0
    checked_flag: int = 0

    gapless_data: int = 0
    gapless_track_flag: int = 0
    gapless_album_flag: int = 0
    pregap: int = 0
    postgap: int = 0
    sample_count: int = 0
    encoder_flag: int = 0

    skip_when_shuffling: bool = False
    remember_position: bool = False
    podcast_flag: int = 0
    movie_file_flag: int = 0
    played_mark: int = -1
    explicit_flag: int = 0
    purchased_aac_flag: int = 0
    has_lyrics: bool = False
    lyrics: str | None = None
    eq_setting: str | None = None

    date_added: int = 0
    date_released: int = 0
    last_modified: int = 0
    last_played: int = 0
    last_skipped: int = 0

    track_id: int = 0
    db_track_id: int = 0
    media_type: int = MEDIA_TYPE_AUDIO
    season_number: int = 0
    episode_number: int = 0
    artwork_count: int = 0
    artwork_size: int = 0
    mhii_link: int = 0
    album_id: int = 0
    source_path: str | None = None
    source_relative_path: str | None = None

    sort_artist: str | None = None
    sort_name: str | None = None
    sort_album: str | None = None
    sort_album_artist: str | None = None
    sort_composer: str | None = None

    grouping: str | None = None
    keywords: str | None = None

    podcast_enclosure_url: str | None = None
    podcast_rss_url: str | None = None
    category: str | None = None

    description: str | None = None
    subtitle: str | None = None
    show_name: str | None = None
    episode_id: str | None = None
    network_name: str | None = None
    sort_show: str | None = None
    show_locale: str | None = None

    filetype_desc: str | None = None

    user_id: int = 0
    app_rating: int = 0
    mpeg_audio_type: int = 0

    date_added_to_itunes: int = 0
    store_track_id: int = 0
    store_encoder_version: int = 0
    store_artist_id: int = 0
    store_album_id: int = 0
    store_content_flag: int = 0

    artist_id: int = 0
    composer_id: int = 0

    chapter_data: dict | None = None

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

    playlist_id: int | None = None
    master: bool = False
    sortorder: int = 0
    podcast_flag: int = 0

    smart_prefs: SmartPlaylistPrefs | None = None
    smart_rules: SmartPlaylistRules | None = None

    mhsd5_type: int = 0

    phase_game_flag: int = 0

    raw_mhod100: bytes | None = None
    raw_mhod102: bytes | None = None
    raw_mhod55: bytes | None = None
    playlist_description: str | None = None

    item_metadata: list[PlaylistItemMeta] | None = None

    @property
    def is_smart(self) -> bool:
        return self.smart_prefs is not None and self.smart_rules is not None
