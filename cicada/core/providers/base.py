"""Interfaz genérica de proveedor de música (ver docs/MUSIC_PROVIDERS.md §4).

Todo proveedor resuelve metadata de playlists/tracks de su servicio; ninguno
descarga audio "de sí mismo" — eso es responsabilidad compartida de
cicada.core.audio_downloader.AudioDownloader, contra YouTube, para todos.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, TypedDict


class TrackMeta(TypedDict, total=False):
    title: str
    artist: str
    album: str
    artwork_url: str
    track_number: int
    original_release_date: str
    external_ids: Dict[str, str]   # {"isrc": "..."} — para matching robusto
    bpm: float
    provider_track_id: str         # id nativo del proveedor (descarga exacta si aplica)


class PlaylistMeta(TypedDict, total=False):
    id: str
    name: str
    description: str
    track_count: int
    image_url: str
    is_liked: bool


class MusicProvider(ABC):
    """Cada proveedor concreto (Spotify, YouTube Music, ...) declara sus dos
    flags como atributos de clase, no como métodos: son hechos fijos sobre el
    servicio, no comportamiento que dependa de estado en tiempo de ejecución.

    `requires_auth_for_own_library` es la señal que debe consultar cualquier
    caller (UI incluida) para decidir si ofrecer "mis playlists" — no el
    NotImplementedError de get_user_playlists(), que es la red de seguridad
    para un caller que no consultó el flag, no el mecanismo principal.
    """

    name: str
    supports_public_playlist_by_id: bool
    requires_auth_for_own_library: bool

    @abstractmethod
    def parse_url(self, url: str) -> Tuple[str, str]:
        """(resource_type, resource_id) a partir de una URL/ID pegado por el usuario."""
        ...

    @abstractmethod
    async def get_tracks(self, resource_type: str, resource_id: str) -> List[TrackMeta]:
        """Metadata de tracks de un recurso, público o ya autenticado según el proveedor."""
        ...

    @abstractmethod
    async def get_user_playlists(self) -> List[PlaylistMeta]:
        """Solo válido si requires_auth_for_own_library and is_authenticated().
        Si el proveedor no soporta esto todavía, debe declarar
        requires_auth_for_own_library en consecuencia para que el caller ni
        llegue a invocar este método; de llegar a invocarse igual, levanta
        NotImplementedError."""
        ...

    @abstractmethod
    def is_authenticated(self) -> bool:
        ...
