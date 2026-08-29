"""Interfaz base para proveedores de música."""
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
    supported_resource_types: Tuple[str, ...]
    """Qué resource_type puede devolver parse_url() y aceptar get_tracks() para
    este proveedor. No todos comparten el mismo espacio de recursos: Spotify
    soporta ("track", "album", "playlist", "collection"), pero YouTube Music
    solo ("playlist") en este alcance — un álbum de YT Music vive en un
    browseId de otro tipo (MPREb_...), no en el espacio de IDs de playlist.
    Un caller (UI o endpoint) debe consultar esto antes de llamar a
    get_tracks() con un resource_type que no está en la tupla, en vez de
    confiar en que get_tracks() lo rechace en tiempo de ejecución — el
    ValueError que get_tracks() lanza para un tipo no soportado es la red de
    seguridad, no el mecanismo principal de validación."""

    @abstractmethod
    def parse_url(self, url: str) -> Tuple[str, str]:
        """(resource_type, resource_id) a partir de una URL/ID pegado por el usuario.
        resource_type siempre pertenece a supported_resource_types."""
        ...

    @abstractmethod
    async def get_tracks(self, resource_type: str, resource_id: str) -> List[TrackMeta]:
        """Metadata de tracks de un recurso, público o ya autenticado según el proveedor.
        Lanza ValueError si resource_type no está en supported_resource_types —
        red de seguridad; el caller debería validar contra ese flag antes."""
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
