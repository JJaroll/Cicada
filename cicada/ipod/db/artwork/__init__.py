"""Escritor de ArtworkDB/.ithmb del iPod (Fase 4).

Alcance actual: solo iPod Nano 7G / RGB565_LE (ver docs/VENDORED.md,
Paquete 7, y docs/IPOD_INTEGRATION.md, Fase 4 — Etapa 4f generaliza a
otros modelos/formatos de píxel más adelante).
"""
from __future__ import annotations

from cicada.ipod.db.artwork.chunks import (
    ParsedFormatRef,
    ParsedImageEntry,
    build_artworkdb,
    read_artworkdb,
)
from cicada.ipod.db.artwork.rgb565 import (
    convert_art_for_format,
    image_from_bytes,
    resize_for_format,
    rgb565_le_to_rgb888,
    rgb888_to_rgb565_le,
)
from cicada.ipod.db.artwork.types import EncodedFormatPayload
from cicada.ipod.db.artwork.writer import (
    ArtworkBuildResult,
    ArtworkSourceTrack,
    ArtworkTrackResult,
    build_artwork_assets,
)

__all__ = [
    "EncodedFormatPayload",
    "convert_art_for_format",
    "image_from_bytes",
    "resize_for_format",
    "rgb565_le_to_rgb888",
    "rgb888_to_rgb565_le",
    "build_artworkdb",
    "read_artworkdb",
    "ParsedFormatRef",
    "ParsedImageEntry",
    "ArtworkBuildResult",
    "ArtworkSourceTrack",
    "ArtworkTrackResult",
    "build_artwork_assets",
]
