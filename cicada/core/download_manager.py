import base64
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, quote

import httpx

from cicada.core.app_paths import get_app_data_dir
from cicada.core.audio_downloader import AudioDownloader
from cicada.core.providers.base import MusicProvider, PlaylistMeta, TrackMeta

logger = logging.getLogger(__name__)

_SPOTIFY_URL_RE = re.compile(
    r"open\.spotify\.com/(?:intl-\w+/)?(track|album|playlist|collection)(?:/([a-zA-Z0-9_-]+))?"
)
_SPOTIFY_URI_RE = re.compile(
    r"spotify:(track|album|playlist|collection|user:[^:]+:collection)(?::([a-zA-Z0-9_-]+))?"
)


class DownloadManager(MusicProvider):
    """
    Gestor de descargas de Cicada.
    Resuelve tracks/álbumes/playlists de Spotify vía el flujo OAuth2
    "Authorization Code" (login del usuario, requerido por Spotify para leer
    playlists privadas/colaborativas y canciones guardadas) contra la API oficial,
    y descarga su audio correspondiente desde YouTube Music.

    Implementa MusicProvider (docs/MUSIC_PROVIDERS.md §4) sobre su propia API
    pública ya existente (get_spotify_tracks/get_user_playlists) — parse_url()
    y get_tracks() son wrappers nuevos, _parse_spotify_url() y
    get_spotify_tracks() no se tocan porque tests y callers ya los usan
    directamente.
    """

    name = "spotify"
    supports_public_playlist_by_id = True   # Client Credentials — ver docs/MUSIC_PROVIDERS.md §1
    requires_auth_for_own_library = True
    supported_resource_types = ("track", "album", "playlist", "collection")

    AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    REDIRECT_URI = "http://127.0.0.1:8000/api/auth/callback"
    SCOPE = "playlist-read-private playlist-read-collaborative user-library-read user-read-private"

    TOKEN_FILE = get_app_data_dir() / ".spotify_token.json"
    TOKEN_EXPIRY_MARGIN_SECONDS = 60

    def __init__(self) -> None:
        self._audio_downloader = AudioDownloader()

    @staticmethod
    def _get_client_credentials() -> Tuple[str, str]:
        client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise ValueError("Faltan las claves SPOTIFY_CLIENT_ID o SPOTIFY_CLIENT_SECRET en el archivo .env")
        return client_id, client_secret

    @staticmethod
    def _basic_auth_header(client_id: str, client_secret: str) -> Dict[str, str]:
        raw = f"{client_id}:{client_secret}".encode("utf-8")
        encoded = base64.b64encode(raw).decode("utf-8")
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def get_auth_url(self) -> str:
        client_id, _ = self._get_client_credentials()
        params = {
            "response_type": "code",
            "client_id": client_id,
            "scope": self.SCOPE,
            "redirect_uri": self.REDIRECT_URI,
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params, quote_via=quote)}"

    def _load_token_data(self) -> Dict[str, Any]:
        if not self.TOKEN_FILE.exists():
            return {}
        try:
            return json.loads(self.TOKEN_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_token_data(self, token_response: Dict[str, Any]) -> Dict[str, Any]:
        previous = self._load_token_data()
        refresh_token = token_response.get("refresh_token") or previous.get("refresh_token")
        if not refresh_token:
            raise ValueError("Spotify no devolvió un refresh_token y no había ninguno guardado previamente.")

        payload = {
            "access_token": token_response["access_token"],
            "refresh_token": refresh_token,
            "expires_at": time.time() + token_response.get("expires_in", 3600),
        }
        self.TOKEN_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    async def process_auth_code(self, code: str) -> None:
        client_id, client_secret = self._get_client_credentials()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.REDIRECT_URI,
        }
        headers = self._basic_auth_header(client_id, client_secret)

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self.TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()
            token_response = response.json()

        self._save_token_data(token_response)

    async def _refresh_user_token(self, refresh_token: str) -> str:
        client_id, client_secret = self._get_client_credentials()
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        headers = self._basic_auth_header(client_id, client_secret)

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self.TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()
            token_response = response.json()

        saved = self._save_token_data(token_response)
        return saved["access_token"]

    async def get_user_token(self) -> str:
        token_data = self._load_token_data()
        if not token_data.get("refresh_token"):
            raise ValueError(
                "No hay una sesión de Spotify iniciada. "
                "Visita http://127.0.0.1:8000/api/auth/login para autorizar el acceso a tus playlists."
            )

        expires_at = token_data.get("expires_at", 0)
        if time.time() < expires_at - self.TOKEN_EXPIRY_MARGIN_SECONDS:
            return token_data["access_token"]

        return await self._refresh_user_token(token_data["refresh_token"])

    @staticmethod
    def _parse_spotify_url(spotify_url: str) -> Tuple[str, str]:
        cleaned = spotify_url.strip()
        if cleaned in ("liked-songs", "collection/tracks", "spotify:collection:tracks", "collection:tracks", "liked"):
            return "collection", "tracks"

        match = _SPOTIFY_URL_RE.search(cleaned)
        if match:
            res_type = match.group(1)
            res_id = match.group(2) or ("tracks" if res_type == "collection" else "")
            return res_type, res_id

        uri_match = _SPOTIFY_URI_RE.search(cleaned)
        if uri_match:
            res_type = uri_match.group(1)
            if "collection" in res_type:
                return "collection", "tracks"
            return res_type, uri_match.group(2) or ""

        raise ValueError(f"URL de Spotify no reconocida (se esperaba track/album/playlist/collection): {spotify_url}")

    @staticmethod
    def _first_artist(artists: Optional[List[dict]]) -> str:
        if not artists:
            return "Unknown Artist"
        return artists[0].get("name") or "Unknown Artist"

    @staticmethod
    def _best_image(images: Optional[List[dict]]) -> str:
        if not images:
            return ""
        return max(images, key=lambda img: img.get("width") or 0).get("url", "")

    def _parse_track_item(self, track: dict) -> Dict[str, Any]:
        album = track.get("album") or {}
        result: Dict[str, Any] = {
            "title": track.get("name", ""),
            "artist": self._first_artist(track.get("artists")),
            "artwork_url": self._best_image(album.get("images")),
        }

        album_name = album.get("name")
        if album_name:
            result["album"] = album_name

        track_number = track.get("track_number")
        if track_number:
            result["track_number"] = track_number

        isrc = (track.get("external_ids") or {}).get("isrc")
        if isrc:
            result["external_ids"] = {"isrc": isrc}

        release_date = album.get("release_date")
        if release_date:
            result["original_release_date"] = release_date

        return result

    async def _fetch_full_tracks(self, client: httpx.AsyncClient, track_ids: List[str], headers: dict) -> Dict[str, dict]:
        full_by_id: Dict[str, dict] = {}
        ids = [tid for tid in track_ids if tid]
        if not ids:
            return full_by_id

        url = "https://api.spotify.com/v1/tracks"
        for i in range(0, len(ids), 50):
            chunk = ids[i:i + 50]
            try:
                response = await client.get(url, headers=headers, params={"ids": ",".join(chunk)})
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.warning(f"No se pudo completar ISRC de álbum (/v1/tracks por lote), se omite ese campo: {e}")
                return full_by_id
            data = response.json()
            for t in data.get("tracks") or []:
                if t and t.get("id"):
                    full_by_id[t["id"]] = t
        return full_by_id

    async def _fetch_bpm_map(self, client: httpx.AsyncClient, track_ids: List[str], headers: dict) -> Dict[str, float]:
        # Spotify restringió /v1/audio-features a apps creadas antes del
        # 27-nov-2024 (ver docs/MUSIC_PROVIDERS.md §1). Si el usuario configura
        # credenciales de una app nueva, este endpoint da 403 para todo el
        # mundo: no es un bug, el try/except de abajo lo tolera devolviendo
        # el mapa vacío y el BPM simplemente no llega a los tracks.
        bpm_by_id: Dict[str, float] = {}
        ids = [tid for tid in track_ids if tid]
        if not ids:
            return bpm_by_id

        url = "https://api.spotify.com/v1/audio-features"
        for i in range(0, len(ids), 100):
            chunk = ids[i:i + 100]
            try:
                response = await client.get(url, headers=headers, params={"ids": ",".join(chunk)})
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.warning(f"No se pudo obtener BPM (audio-features) de Spotify, se omite ese campo: {e}")
                return bpm_by_id
            data = response.json()
            for feature in data.get("audio_features") or []:
                if feature and feature.get("id") and feature.get("tempo") is not None:
                    bpm_by_id[feature["id"]] = round(feature["tempo"])
        return bpm_by_id

    async def _fetch_paginated_items(self, client: httpx.AsyncClient, first_next: Optional[str], headers: dict, initial_items: List[dict]) -> List[dict]:
        items = list(initial_items)
        next_url = first_next
        while next_url:
            page = await client.get(next_url, headers=headers)
            page.raise_for_status()
            page_data = page.json()
            items.extend(page_data.get("items", []))
            next_url = page_data.get("next")
        return items

    async def _fetch_album_tracks(self, client: httpx.AsyncClient, album_id: str, headers: dict) -> List[Dict[str, Any]]:
        response = await client.get(f"https://api.spotify.com/v1/albums/{album_id}", headers=headers)
        response.raise_for_status()
        data = response.json()

        artwork_url = self._best_image(data.get("images"))
        album_name = data.get("name") or ""
        album_release_date = data.get("release_date") or ""
        tracks_obj = data.get("tracks", {})
        items = await self._fetch_paginated_items(client, tracks_obj.get("next"), headers, tracks_obj.get("items", []))

        track_ids = [item.get("id") for item in items if item]
        full_tracks = await self._fetch_full_tracks(client, track_ids, headers)
        bpm_map = await self._fetch_bpm_map(client, track_ids, headers)

        tracks = []
        for item in items:
            if not item:
                continue

            track: Dict[str, Any] = {
                "title": item.get("name", ""),
                "artist": self._first_artist(item.get("artists")),
                "artwork_url": artwork_url,
            }
            if album_name:
                track["album"] = album_name
            if album_release_date:
                track["original_release_date"] = album_release_date
            track_number = item.get("track_number")
            if track_number:
                track["track_number"] = track_number

            full = full_tracks.get(item.get("id"))
            isrc = (full.get("external_ids") or {}).get("isrc") if full else None
            if isrc:
                track["external_ids"] = {"isrc": isrc}

            bpm = bpm_map.get(item.get("id"))
            if bpm is not None:
                track["bpm"] = bpm

            tracks.append(track)
        return tracks

    async def _fetch_playlist_tracks(self, client: httpx.AsyncClient, playlist_id: str, headers: dict) -> List[Dict[str, Any]]:
        response = await client.get(f"https://api.spotify.com/v1/playlists/{playlist_id}/items", headers=headers)
        response.raise_for_status()
        data = response.json()

        items = await self._fetch_paginated_items(client, data.get("next"), headers, data.get("items", []))

        valid_tracks = [
            t for t in ((item or {}).get("item") or (item or {}).get("track") for item in items) if t
        ]

        track_ids = [t.get("id") for t in valid_tracks]
        bpm_map = await self._fetch_bpm_map(client, track_ids, headers)

        tracks = []
        for track_data in valid_tracks:
            parsed = self._parse_track_item(track_data)
            bpm = bpm_map.get(track_data.get("id"))
            if bpm is not None:
                parsed["bpm"] = bpm
            tracks.append(parsed)

        return tracks

    async def _fetch_saved_tracks(self, client: httpx.AsyncClient, headers: dict) -> List[Dict[str, Any]]:
        try:
            response = await client.get("https://api.spotify.com/v1/me/tracks", headers=headers, params={"limit": 50})
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                raise ValueError(
                    "No se pudo acceder a tus 'Canciones que te gustan'. "
                    "Por favor, reconecta tu cuenta de Spotify en la aplicación para autorizar el permiso 'user-library-read'."
                ) from e
            raise

        data = response.json()
        items = await self._fetch_paginated_items(client, data.get("next"), headers, data.get("items", []))

        valid_tracks = [
            item.get("track") for item in items if item and item.get("track")
        ]

        track_ids = [t.get("id") for t in valid_tracks if t and t.get("id")]
        bpm_map = await self._fetch_bpm_map(client, track_ids, headers)

        tracks = []
        for track_data in valid_tracks:
            if not track_data:
                continue
            parsed = self._parse_track_item(track_data)
            bpm = bpm_map.get(track_data.get("id"))
            if bpm is not None:
                parsed["bpm"] = bpm
            tracks.append(parsed)

        return tracks

    async def get_user_playlists(self) -> List[Dict[str, Any]]:
        token = await self.get_user_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Obtener ID del usuario actual para filtrar solo playlists propias o colaborativas
            current_user_id = None
            try:
                user_res = await client.get("https://api.spotify.com/v1/me", headers=headers)
                if user_res.status_code == 200:
                    current_user_id = user_res.json().get("id")
            except Exception as e:
                logger.warning(f"No se pudo obtener el ID del usuario actual de Spotify: {e}")

            # 2. Consultar conteo de 'Canciones que te gustan' (Saved Tracks)
            liked_count = 0
            has_liked_songs = False
            try:
                liked_res = await client.get("https://api.spotify.com/v1/me/tracks", headers=headers, params={"limit": 1})
                if liked_res.status_code == 200:
                    liked_data = liked_res.json()
                    liked_count = liked_data.get("total", 0)
                    has_liked_songs = True
            except Exception as e:
                logger.warning(f"No se pudo consultar 'Canciones que te gustan' (posible falta de scope user-library-read): {e}")

            # 3. Consultar playlists del usuario
            response = await client.get(
                "https://api.spotify.com/v1/me/playlists",
                headers=headers,
                params={"limit": 50},
            )
            response.raise_for_status()
            data = response.json()

            items = await self._fetch_paginated_items(client, data.get("next"), headers, data.get("items", []))

        playlists = []

        # Agregar entrada especial para "Canciones que te gustan" al inicio
        if has_liked_songs:
            playlists.append({
                "id": "liked-songs",
                "name": "Canciones que te gustan",
                "description": "Tus canciones favoritas guardadas en Spotify",
                "track_count": liked_count,
                "image_url": "",
                "is_liked": True,
            })

        for item in items:
            if not item:
                continue

            owner_id = (item.get("owner") or {}).get("id")
            is_collaborative = bool(item.get("collaborative"))

            # Filtrar: solo playlists creadas por el propio usuario o donde es colaborador
            if current_user_id and owner_id and owner_id != current_user_id and not is_collaborative:
                continue

            playlists.append({
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "description": item.get("description") or "",
                "track_count": (item.get("items") or item.get("tracks") or {}).get("total", 0),
                "image_url": self._best_image(item.get("images")),
                "is_liked": False,
            })
        return playlists

    async def get_spotify_tracks(self, spotify_url: str) -> List[Dict[str, Any]]:
        resource_type, resource_id = self._parse_spotify_url(spotify_url)
        return await self._fetch_tracks_for_resource(resource_type, resource_id)

    async def _fetch_tracks_for_resource(self, resource_type: str, resource_id: str) -> List[Dict[str, Any]]:
        token = await self.get_user_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            if resource_type in ("collection", "liked") or resource_id in ("liked-songs", "tracks"):
                if resource_type == "collection" or resource_id == "liked-songs":
                    return await self._fetch_saved_tracks(client, headers)

            if resource_type == "track":
                response = await client.get(f"https://api.spotify.com/v1/tracks/{resource_id}", headers=headers)
                response.raise_for_status()
                track_data = response.json()
                parsed = self._parse_track_item(track_data)

                bpm_map = await self._fetch_bpm_map(client, [track_data.get("id")], headers)
                bpm = bpm_map.get(track_data.get("id"))
                if bpm is not None:
                    parsed["bpm"] = bpm

                return [parsed]

            if resource_type == "album":
                return await self._fetch_album_tracks(client, resource_id, headers)

            if resource_type == "playlist":
                return await self._fetch_playlist_tracks(client, resource_id, headers)

        raise ValueError(f"Tipo de recurso de Spotify no soportado: {resource_type}")

    # --- Implementación de MusicProvider (docs/MUSIC_PROVIDERS.md §4) ---
    # Wrappers sobre la API ya existente arriba; ningún método/nombre previo
    # se renombra ni se elimina.

    def parse_url(self, url: str) -> Tuple[str, str]:
        return self._parse_spotify_url(url)

    async def get_tracks(self, resource_type: str, resource_id: str) -> List[TrackMeta]:
        return await self._fetch_tracks_for_resource(resource_type, resource_id)  # type: ignore[return-value]

    def is_authenticated(self) -> bool:
        return self.TOKEN_FILE.exists()

    async def download_audio(self, query: str, download_path: str) -> str:
        return await self._audio_downloader.download_audio(query, download_path)
