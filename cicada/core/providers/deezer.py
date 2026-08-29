"""Proveedor de Deezer (ver docs/MUSIC_PROVIDERS.md §4-5, prioridad 2).

Solo cubre el camino "playlist/álbum/track público por ID, sin login" — la
API pública de Deezer no exige ninguna clave para esto. "Mis playlists"
(requiere OAuth de usuario) queda diferido: el estado real del registro de
apps nuevas de Deezer no está confirmado (fuentes contradictorias, ver
docs/MUSIC_PROVIDERS.md) y no se investigó más a fondo porque no cambia el
alcance de este corte.

Deezer es solo metadata, igual que Spotify: no aloja audio descargable (el
campo "preview" es un clip de 30s firmado, no la pista completa). La
descarga real sigue siendo la búsqueda heurística en YouTube vía
AudioDownloader — no hay un id exacto de video como con YouTube Music.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

import httpx

from cicada.core.providers.base import MusicProvider, PlaylistMeta, TrackMeta

logger = logging.getLogger(__name__)

_API_BASE = "https://api.deezer.com"

_URL_RE = re.compile(
    r"deezer\.com/(?:[a-z]{2}/)?(track|album|playlist)/(\d+)"
)
_BARE_ID_RE = re.compile(r"^\d+$")


class DeezerProvider(MusicProvider):
    """Metadata de tracks/álbumes/playlists públicos de Deezer, sin auth.
    BPM deliberadamente no incluido en TrackMeta: el campo existe en la API
    pero viene sistemáticamente en 0 en las muestras verificadas — prometerlo
    en el modelo cuando en la práctica nunca llega es peor que omitirlo.
    """

    name = "deezer"
    supports_public_playlist_by_id = True
    requires_auth_for_own_library = True
    supported_resource_types = ("track", "album", "playlist")

    def __init__(self) -> None:
        pass

    def parse_url(self, url: str) -> Tuple[str, str]:
        cleaned = url.strip()

        match = _URL_RE.search(cleaned)
        if match:
            return match.group(1), match.group(2)

        if _BARE_ID_RE.match(cleaned):
            # Un ID numérico suelto no indica su tipo por sí mismo; se asume
            # playlist, el caso de uso principal (mismo criterio que YouTube
            # Music con un ID de playlist suelto). Para track/álbum, el
            # caller debe pasar la URL completa.
            return "playlist", cleaned

        raise ValueError(
            f"URL/ID de Deezer no reconocido (se esperaba track/album/playlist): {url}"
        )

    async def get_tracks(self, resource_type: str, resource_id: str) -> List[TrackMeta]:
        if resource_type not in self.supported_resource_types:
            raise ValueError(
                f"Deezer solo soporta {self.supported_resource_types} en este "
                f"alcance, no '{resource_type}'."
            )

        async with httpx.AsyncClient(timeout=15.0) as client:
            if resource_type == "track":
                response = await client.get(f"{_API_BASE}/track/{resource_id}")
                response.raise_for_status()
                data = response.json()
                if data.get("error"):
                    raise ValueError(f"Deezer no encontró el track {resource_id}: {data['error']}")
                return [self._parse_track_item(data)]

            # album y playlist comparten la misma forma de "tracklist paginado",
            # pero /album/{id}/tracks, a diferencia de /playlist/{id}/tracks, no
            # repite el objeto "album" completo en cada item — solo track_position/
            # disk_number. Para álbum, se completa título/carátula por separado.
            album_meta: Optional[dict] = None
            if resource_type == "album":
                album_response = await client.get(f"{_API_BASE}/album/{resource_id}")
                album_response.raise_for_status()
                album_meta = album_response.json()
                if album_meta.get("error"):
                    raise ValueError(f"Deezer no encontró el álbum {resource_id}: {album_meta['error']}")

            endpoint = f"{_API_BASE}/{resource_type}/{resource_id}/tracks"
            response = await client.get(endpoint)
            response.raise_for_status()
            data = response.json()
            if data.get("error"):
                raise ValueError(f"Deezer no encontró {resource_type} {resource_id}: {data['error']}")

            items = await self._fetch_paginated_items(client, data)
            tracks = [self._parse_track_item(item) for item in items if item]

            if album_meta is not None:
                for track in tracks:
                    track.setdefault("album", album_meta.get("title", ""))
                    artwork = album_meta.get("cover_xl") or album_meta.get("cover_big")
                    if artwork:
                        track.setdefault("artwork_url", artwork)

            return tracks

    async def _fetch_paginated_items(self, client: httpx.AsyncClient, first_page: dict) -> List[dict]:
        items = list(first_page.get("data", []))
        next_url: Optional[str] = first_page.get("next")
        while next_url:
            page = await client.get(next_url)
            page.raise_for_status()
            page_data = page.json()
            items.extend(page_data.get("data", []))
            next_url = page_data.get("next")
        return items

    @staticmethod
    def _parse_track_item(item: dict) -> TrackMeta:
        track: TrackMeta = {
            "title": item.get("title") or item.get("title_short") or "",
            "artist": (item.get("artist") or {}).get("name") or "Unknown Artist",
            "provider_track_id": str(item.get("id", "")),
        }

        album = item.get("album") or {}
        if album.get("title"):
            track["album"] = album["title"]

        artwork_url = album.get("cover_xl") or album.get("cover_big") or album.get("cover")
        if artwork_url:
            track["artwork_url"] = artwork_url

        isrc = item.get("isrc")
        if isrc:
            track["external_ids"] = {"isrc": isrc}

        return track

    async def get_user_playlists(self) -> List[PlaylistMeta]:
        raise NotImplementedError(
            "DeezerProvider todavía no soporta 'mis playlists' (requiere auth "
            "de usuario; estado del registro de apps de Deezer no confirmado, "
            "ver docs/MUSIC_PROVIDERS.md). Consultar requires_auth_for_own_library "
            "antes de llamar a este método."
        )

    def is_authenticated(self) -> bool:
        return False
