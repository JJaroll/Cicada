"""Tipos internos del escritor de ArtworkDB (Fase 4).

Adaptado de artworkdb_writer/artwork_types.py de iOpenPod. Se excluyen
ExistingFormatRef/PassthroughFormatRef: esos existen ahí para soportar
preservación incremental de arte sin cambios entre syncs, y Cicada 4c
reescribe ArtworkDB completo en cada sync (ver docs/VENDORED.md, Paquete 7)
— no hay "referencia a lo existente" que preservar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class EncodedFormatPayload:
    """Payload de píxeles ya codificado para un format_id concreto."""

    data: bytes
    width: int
    height: int
    size: int
    stride_pixels: int
    hpad: int = 0
    vpad: int = 0
    pixel_format: Optional[str] = None


@dataclass(frozen=True)
class PhotoAlbumInput:
    """Entrada de escritura para un MHBA (Fase 6, Etapa 6f).

    Layout extraído de ``_write_mhba``/``PhotoAlbum`` en ``sync/photos.py``
    de iOpenPod (ver docs/VENDORED.md, Paquete 9). Los campos de
    slideshow/reproducción (``playmusic``/``repeat``/``random``/
    ``show_titles``/``transition_*``/``song_id``) no tienen consumidor en
    Cicada todavía — se aceptan con default 0 (silencio, sin efecto en el
    dispositivo) en vez de omitirse, porque son parte fija del layout
    binario del chunk, no una capacidad opcional de más alto nivel.
    """

    album_id: int
    name: str
    members: Tuple[int, ...] = field(default_factory=tuple)
    album_type: int = 2
    playmusic: int = 0
    repeat: int = 0
    random: int = 0
    show_titles: int = 0
    transition_direction: int = 0
    slide_duration: int = 0
    transition_duration: int = 0
    song_id: int = 0
    prev_album_id: int = 0
