import asyncio
import base64
import json
import logging
import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, quote

import httpx

from app_paths import get_app_data_dir

logger = logging.getLogger(__name__)

# Acepta open.spotify.com/track|album|playlist/{id}, incluyendo variantes con
# locale ("/intl-es/") y query strings ("?si=...") al final.
_SPOTIFY_URL_RE = re.compile(
    r"open\.spotify\.com/(?:intl-\w+/)?(track|album|playlist)/([a-zA-Z0-9]+)"
)


class DownloadManager:
    """
    Gestor de descargas de Cicada.
    Resuelve tracks/álbumes/playlists de Spotify vía el flujo OAuth2
    "Authorization Code" (login del usuario, requerido por Spotify para leer
    playlists privadas/colaborativas) contra la API oficial, y descarga su
    audio correspondiente desde YouTube Music.
    """

    AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    REDIRECT_URI = "http://127.0.0.1:8000/api/auth/callback"
    SCOPE = "playlist-read-private playlist-read-collaborative"

    TOKEN_FILE = get_app_data_dir() / ".spotify_token.json"
    TOKEN_EXPIRY_MARGIN_SECONDS = 60

    def __init__(self) -> None:
        self.upgrade_ytdlp()

    def upgrade_ytdlp(self) -> None:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
        except Exception as e:
            logger.warning(f"No se pudo auto-actualizar yt-dlp en el inicio: {e}")

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
        match = _SPOTIFY_URL_RE.search(spotify_url)
        if not match:
            raise ValueError(f"URL de Spotify no reconocida (se esperaba track/album/playlist): {spotify_url}")
        return match.group(1), match.group(2)

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

    async def get_user_playlists(self) -> List[Dict[str, Any]]:
        token = await self.get_user_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.spotify.com/v1/me/playlists",
                headers=headers,
                params={"limit": 50},
            )
            response.raise_for_status()
            data = response.json()

            items = await self._fetch_paginated_items(client, data.get("next"), headers, data.get("items", []))

        playlists = []
        for item in items:
            if not item:
                continue
            playlists.append({
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "description": item.get("description") or "",
                # Spotify migró el campo "tracks" a "items" en el objeto de playlist simplificado; probamos ambos.
                "track_count": (item.get("items") or item.get("tracks") or {}).get("total", 0),
                "image_url": self._best_image(item.get("images")),
            })
        return playlists

    async def get_spotify_tracks(self, spotify_url: str) -> List[Dict[str, Any]]:
        resource_type, resource_id = self._parse_spotify_url(spotify_url)
        token = await self.get_user_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
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

    def _sync_download(self, query: str, download_path: str) -> str:
        import yt_dlp

        os.makedirs(download_path, exist_ok=True)

        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
            'playlist_items': '1',
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if not info:
                raise RuntimeError(f"No se obtuvieron resultados de búsqueda para: '{query}'")

            if 'entries' in info:
                if not info['entries']:
                    raise RuntimeError(f"La búsqueda en YouTube no retornó resultados para: '{query}'")
                video_info = info['entries'][0]
            else:
                video_info = info

            temp_filename = ydl.prepare_filename(video_info)

            base_path, _ = os.path.splitext(temp_filename)
            final_path = f"{base_path}.m4a"

            if not os.path.exists(final_path):
                if os.path.exists(temp_filename):
                    final_path = temp_filename
                else:
                    basename = os.path.basename(base_path)
                    matching_files = [
                        os.path.join(download_path, f)
                        for f in os.listdir(download_path)
                        if f.startswith(basename)
                    ]
                    if matching_files:
                        final_path = matching_files[0]
                    else:
                        raise FileNotFoundError(
                            f"No se pudo encontrar el archivo descargado final: {final_path} (temp: {temp_filename})"
                        )

            return os.path.abspath(final_path)

    async def download_audio(self, query: str, download_path: str) -> str:
        return await asyncio.to_thread(self._sync_download, query, download_path)
