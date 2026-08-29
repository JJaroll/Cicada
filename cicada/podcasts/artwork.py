"""Descarga y embebido de carátulas para episodios de podcasts."""
from __future__ import annotations

import io
import logging
from pathlib import Path

import httpx
from PIL import Image, UnidentifiedImageError

log = logging.getLogger(__name__)

_TIMEOUT = 15.0
_MAX_DIMENSION = 1400
_JPEG_QUALITY = 90

_EMBEDDABLE_EXTS = {".mp3", ".m4a", ".m4b", ".aac"}


def prepare_artwork_bytes(data: bytes) -> bytes | None:
    # Prepara bytes de imagen JPEG para ser embebidos.
    if not data or len(data) < 64:
        return None

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            rgba = img.convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError):
        return None

    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    background.alpha_composite(rgba)
    rgb = background.convert("RGB")
    if max(rgb.size) > _MAX_DIMENSION:
        rgb.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    rgb.save(out, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    prepared = out.getvalue()
    return prepared if len(prepared) >= 64 else None


async def embed_artwork(file_path: str, artwork_url: str) -> bool:
    # Descarga y embebe la carátula en el audio.
    if not artwork_url:
        return False

    ext = Path(file_path).suffix.lower()
    if ext not in _EMBEDDABLE_EXTS:
        return False

    try:
        from mutagen import File as MutagenFile

        audio = MutagenFile(file_path)
        if audio is None:
            return False

        if ext == ".mp3":
            if any(k.startswith("APIC") for k in (audio.tags or {})):
                return False
        elif hasattr(audio, "tags") and audio.tags and "covr" in audio.tags:
            return False
    except Exception as exc:
        log.debug("No se pudo inspeccionar artwork de %s: %s", file_path, exc)
        return False

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
            resp = await client.get(
                artwork_url, headers={"User-Agent": "Cicada (Podcast Manager)"}
            )
            resp.raise_for_status()
            art_data = resp.content
    except Exception as exc:
        log.debug("No se pudo descargar artwork %s: %s", artwork_url, exc)
        return False

    prepared = prepare_artwork_bytes(art_data)
    if not prepared:
        return False

    try:
        if ext == ".mp3":
            from mutagen.id3 import APIC, PictureType

            if audio.tags is None:
                audio.add_tags()
            audio.tags.add(APIC(
                encoding=0,
                mime="image/jpeg",
                type=PictureType.COVER_FRONT,
                desc="Cover",
                data=prepared,
            ))
            audio.save()
        else:
            from mutagen.mp4 import MP4Cover

            if audio.tags is None:
                audio.add_tags()
            audio.tags["covr"] = [MP4Cover(prepared, imageformat=MP4Cover.FORMAT_JPEG)]
            audio.save()
    except Exception as exc:
        log.debug("No se pudo embeber artwork en %s: %s", file_path, exc)
        return False

    log.info("Artwork del feed embebido en %s", Path(file_path).name)
    return True
