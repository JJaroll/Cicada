"""Proveedor de YouTube Music (ver docs/MUSIC_PROVIDERS.md §4-5, prioridad 1).

Solo cubre el camino "playlist pública por ID, sin login" — ytmusicapi sin
credenciales. La auth de "mis playlists" (cookies de sesión / device code)
queda diferida: requires_auth_for_own_library = True ya se lo comunica a
cualquier caller, get_user_playlists() es la red de seguridad, no el
mecanismo principal de control de flujo (ver confirmación del usuario en
docs/MUSIC_PROVIDERS.md).
"""
from __future__ import annotations

import logging
import re
from typing import List, Tuple

from ytmusicapi import YTMusic

from cicada.core.providers.base import MusicProvider, PlaylistMeta, TrackMeta

logger = logging.getLogger(__name__)

_TRACK_URL_RE = re.compile(
    r"(?:(?:music|www|m)\.)?(?:youtube\.com/watch\?(?:.*&)?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
)
_ALBUM_URL_RE = re.compile(
    r"(?:music\.)?youtube\.com/browse/(MPREb_[a-zA-Z0-9_-]+)"
)
_PLAYLIST_URL_RE = re.compile(
    r"(?:(?:music|www|m)\.)?youtube\.com/playlist\?(?:.*&)?list=([a-zA-Z0-9_-]+)"
)
_BARE_ALBUM_ID_RE = re.compile(r"^MPREb_[a-zA-Z0-9_-]+$")
_BARE_PLAYLIST_ID_RE = re.compile(r"^(?:VL)?(?:PL|OLAK5uy_|RD)[a-zA-Z0-9_-]+$")
_BARE_VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


class YouTubeMusicProvider(MusicProvider):
    """Metadata de tracks, álbumes y playlists públicas de YouTube Music, sin auth de usuario.
    La descarga real de audio se hace aparte con AudioDownloader, usando el
    videoId exacto (provider_track_id) en vez de una búsqueda por texto.
    """

    name = "youtube_music"
    supports_public_playlist_by_id = True
    requires_auth_for_own_library = True
    supported_resource_types = ("track", "album", "playlist")

    def __init__(self) -> None:
        self._yt = YTMusic()

    def parse_url(self, url: str) -> Tuple[str, str]:
        cleaned = url.strip()

        match_track = _TRACK_URL_RE.search(cleaned)
        if match_track:
            return "track", match_track.group(1)

        match_album = _ALBUM_URL_RE.search(cleaned)
        if match_album:
            return "album", match_album.group(1)

        match_playlist = _PLAYLIST_URL_RE.search(cleaned)
        if match_playlist:
            return "playlist", self._strip_browse_prefix(match_playlist.group(1))

        if _BARE_ALBUM_ID_RE.match(cleaned):
            return "album", cleaned

        if _BARE_PLAYLIST_ID_RE.match(cleaned):
            return "playlist", self._strip_browse_prefix(cleaned)

        if _BARE_VIDEO_ID_RE.match(cleaned):
            return "track", cleaned

        raise ValueError(
            f"URL/ID de YouTube Music no reconocido (se esperaba track/album/playlist): {url}"
        )

    @staticmethod
    def _strip_browse_prefix(playlist_id: str) -> str:
        # yt.search() devuelve browseId con prefijo "VL" (p.ej. resultados de
        # búsqueda de playlists); get_playlist() espera el id sin ese
        # prefijo, que es la forma en que aparece en la URL real que un
        # usuario pegaría (music.youtube.com/playlist?list=PLxxxx).
        return playlist_id[2:] if playlist_id.startswith("VL") else playlist_id

    async def get_tracks(self, resource_type: str, resource_id: str) -> List[TrackMeta]:
        if resource_type not in self.supported_resource_types:
            raise ValueError(
                f"YouTube Music solo soporta {self.supported_resource_types} en este "
                f"alcance, no '{resource_type}'."
            )

        if resource_type == "track":
            return self._get_single_track(resource_id)
        elif resource_type == "album":
            return self._get_album_tracks(resource_id)
        else:
            return self._get_playlist_tracks(resource_id)

    def _get_single_track(self, video_id: str) -> List[TrackMeta]:
        try:
            watch = self._yt.get_watch_playlist(video_id)
            if watch.get("tracks"):
                item = watch["tracks"][0]
                artists = item.get("artists") or []
                artist_name = ", ".join(a["name"] for a in artists if a.get("name")) if artists else (item.get("byline") or "Unknown Artist")
                album_info = item.get("album") or {}
                return [{
                    "title": item.get("title") or "",
                    "artist": artist_name,
                    "album": album_info.get("name", ""),
                    "artwork_url": self._best_thumbnail(item.get("thumbnail")),
                    "provider_track_id": video_id,
                }]
        except Exception:
            logger.debug("get_watch_playlist falló para %s, intentando get_song", video_id, exc_info=True)

        song = self._yt.get_song(video_id)
        details = song.get("videoDetails") or {}
        thumbs = (details.get("thumbnail") or {}).get("thumbnails") or []
        return [{
            "title": details.get("title") or "",
            "artist": details.get("author") or "Unknown Artist",
            "artwork_url": self._best_thumbnail(thumbs),
            "provider_track_id": video_id,
        }]

    def _get_album_tracks(self, browse_id: str) -> List[TrackMeta]:
        album = self._yt.get_album(browse_id)
        album_title = album.get("title") or ""
        artwork_url = self._best_thumbnail(album.get("thumbnails"))
        artists = album.get("artists") or []
        default_artist = ", ".join(a["name"] for a in artists if a.get("name")) if artists else "Unknown Artist"

        tracks: List[TrackMeta] = []
        for item in album.get("tracks") or []:
            if not item or not item.get("videoId"):
                continue

            t_artists = item.get("artists") or []
            t_artist = ", ".join(a["name"] for a in t_artists if a.get("name")) if t_artists else default_artist
            track: TrackMeta = {
                "title": item.get("title") or "",
                "artist": t_artist,
                "album": album_title,
                "artwork_url": self._best_thumbnail(item.get("thumbnails")) or artwork_url,
                "provider_track_id": item["videoId"],
            }
            tracks.append(track)

        return tracks

    def _get_playlist_tracks(self, resource_id: str) -> List[TrackMeta]:
        # ytmusicapi es síncrona (usa requests); no hay una versión async
        # oficial, y no vale la pena to_thread() acá porque esto se llama
        # una sola vez por resolución de link, no en un loop caliente.
        playlist = self._yt.get_playlist(resource_id)
        playlist_artwork = self._best_thumbnail(playlist.get("thumbnails"))

        tracks: List[TrackMeta] = []
        for item in playlist.get("tracks") or []:
            if not item or not item.get("videoId"):
                continue

            artists = item.get("artists") or []
            artist_name = ", ".join(a["name"] for a in artists if a.get("name")) if artists else "Unknown Artist"
            track: TrackMeta = {
                "title": item.get("title") or "",
                "artist": artist_name,
                "artwork_url": self._best_thumbnail(item.get("thumbnails")) or playlist_artwork,
                "provider_track_id": item["videoId"],
            }

            album = item.get("album")
            if album and album.get("name"):
                track["album"] = album["name"]

            tracks.append(track)

        return tracks

    @staticmethod
    def _best_thumbnail(thumbnails) -> str:
        if not thumbnails:
            return ""
        if isinstance(thumbnails, list):
            return max(thumbnails, key=lambda t: (t.get("width") or 0) if isinstance(t, dict) else 0).get("url", "")
        return ""

    async def get_user_playlists(self) -> List[PlaylistMeta]:
        raise NotImplementedError(
            "YouTubeMusicProvider todavía no soporta 'mis playlists' (requiere auth "
            "de usuario, diferido — ver docs/MUSIC_PROVIDERS.md). Consultar "
            "requires_auth_for_own_library antes de llamar a este método."
        )

    def is_authenticated(self) -> bool:
        return False
