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

_PLAYLIST_URL_RE = re.compile(
    r"music\.youtube\.com/playlist\?(?:.*&)?list=([a-zA-Z0-9_-]+)"
)
_PLAYLIST_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{10,}$")


class YouTubeMusicProvider(MusicProvider):
    """Metadata de playlists públicas de YouTube Music, sin auth de usuario.
    La descarga real de audio se hace aparte con AudioDownloader, usando el
    videoId exacto (provider_track_id) en vez de una búsqueda por texto.
    """

    name = "youtube_music"
    supports_public_playlist_by_id = True
    requires_auth_for_own_library = True

    def __init__(self) -> None:
        self._yt = YTMusic()

    def parse_url(self, url: str) -> Tuple[str, str]:
        cleaned = url.strip()

        match = _PLAYLIST_URL_RE.search(cleaned)
        if match:
            return "playlist", self._strip_browse_prefix(match.group(1))

        if _PLAYLIST_ID_RE.match(cleaned):
            return "playlist", self._strip_browse_prefix(cleaned)

        raise ValueError(
            f"URL/ID de playlist de YouTube Music no reconocido: {url}"
        )

    @staticmethod
    def _strip_browse_prefix(playlist_id: str) -> str:
        # yt.search() devuelve browseId con prefijo "VL" (p.ej. resultados de
        # búsqueda de playlists); get_playlist() espera el id sin ese
        # prefijo, que es la forma en que aparece en la URL real que un
        # usuario pegaría (music.youtube.com/playlist?list=PLxxxx).
        return playlist_id[2:] if playlist_id.startswith("VL") else playlist_id

    async def get_tracks(self, resource_type: str, resource_id: str) -> List[TrackMeta]:
        if resource_type != "playlist":
            raise ValueError(
                f"YouTube Music solo soporta 'playlist' en este alcance, no '{resource_type}'."
            )

        # ytmusicapi es síncrona (usa requests); no hay una versión async
        # oficial, y no vale la pena to_thread() acá porque esto se llama
        # una sola vez por resolución de link, no en un loop caliente.
        playlist = self._yt.get_playlist(resource_id)

        tracks: List[TrackMeta] = []
        for item in playlist.get("tracks") or []:
            if not item or not item.get("videoId"):
                continue

            artists = item.get("artists") or []
            track: TrackMeta = {
                "title": item.get("title") or "",
                "artist": artists[0].get("name") if artists else "Unknown Artist",
                "artwork_url": self._best_thumbnail(item.get("thumbnails")),
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
        return max(thumbnails, key=lambda t: t.get("width") or 0).get("url", "")

    async def get_user_playlists(self) -> List[PlaylistMeta]:
        raise NotImplementedError(
            "YouTubeMusicProvider todavía no soporta 'mis playlists' (requiere auth "
            "de usuario, diferido — ver docs/MUSIC_PROVIDERS.md). Consultar "
            "requires_auth_for_own_library antes de llamar a este método."
        )

    def is_authenticated(self) -> bool:
        return False
