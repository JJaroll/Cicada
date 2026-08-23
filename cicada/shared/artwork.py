"""Extracción de carátula embebida en archivos de audio.

Usado por cicada.core (endpoint /api/library/artwork, UI de Biblioteca) y por
el escritor de ArtworkDB del iPod (Fase 4): ambos necesitan la misma carátula
que ya deja audio_processor.py embebida al organizar la biblioteca, así que
no hace falta un segundo sistema de descarga/extracción para el iPod.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple


def extract_embedded_artwork(file_path: Path) -> Tuple[Optional[bytes], Optional[str]]:
    try:
        import mutagen
        from mutagen.mp4 import MP4
        from mutagen.flac import FLAC

        audio = mutagen.File(str(file_path))
        if audio is None:
            return None, None

        if isinstance(audio, MP4):
            covers = audio.tags.get("covr") if audio.tags else None
            if covers:
                cover = covers[0]
                mime = "image/png" if cover.imageformat == cover.FORMAT_PNG else "image/jpeg"
                return bytes(cover), mime
            return None, None

        if isinstance(audio, FLAC):
            if audio.pictures:
                pic = audio.pictures[0]
                return pic.data, pic.mime
            return None, None

        if audio.tags is not None:
            for key in list(audio.tags.keys()):
                if str(key).startswith("APIC"):
                    apic = audio.tags[key]
                    return apic.data, apic.mime

        return None, None
    except Exception:
        return None, None
