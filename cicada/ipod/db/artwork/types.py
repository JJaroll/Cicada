"""Tipos internos del escritor de ArtworkDB (Fase 4).

Adaptado de artworkdb_writer/artwork_types.py de iOpenPod. Se excluyen
ExistingFormatRef/PassthroughFormatRef: esos existen ahí para soportar
preservación incremental de arte sin cambios entre syncs, y Cicada 4c
reescribe ArtworkDB completo en cada sync (ver docs/VENDORED.md, Paquete 7)
— no hay "referencia a lo existente" que preservar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


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
