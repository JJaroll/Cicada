"""Escaneo y extracción de metadatos de audiolibros locales."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mutagen

from cicada.ipod.db.writer.chapter_extraction import extract_chapters

AUDIOBOOK_EXTENSIONS = {".m4b", ".m4a", ".mp3", ".aac"}
_MAX_FILES = 2000
_MAX_DEPTH = 6


def scan_audiobook_folder(root_dir: str) -> Dict[str, Any]:
    # Escanea la carpeta buscando audiolibros y sus metadatos.
    base = Path(root_dir)
    audiobooks: List[Dict[str, Any]] = []
    truncated = False

    if not base.is_dir():
        return {"audiobooks": audiobooks, "count": 0, "truncated": False}

    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        depth = Path(dirpath).relative_to(base).parts
        if len(depth) >= _MAX_DEPTH:
            dirnames[:] = []

        for filename in sorted(filenames):
            file_path = Path(dirpath) / filename
            if file_path.suffix.lower() not in AUDIOBOOK_EXTENSIONS:
                continue

            audiobooks.append(_describe_audiobook(file_path))

            if len(audiobooks) >= _MAX_FILES:
                truncated = True
                break

        if truncated:
            break

    return {"audiobooks": audiobooks, "count": len(audiobooks), "truncated": truncated}


def _describe_audiobook(file_path: Path) -> Dict[str, Any]:
    title, author, narrator = _read_tags(file_path)
    duration_ms = _read_duration_ms(file_path)
    chapters = extract_chapters(str(file_path))

    return {
        "path": str(file_path.resolve()),
        "title": title or file_path.stem,
        "author": author,
        "narrator": narrator,
        "duration_ms": duration_ms,
        "chapter_count": len(chapters) if chapters else None,
        "filetype": file_path.suffix.lstrip(".").lower(),
    }


def _read_tags(file_path: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Título/autor/narrador vía la interfaz 'easy' de mutagen. Nunca lanza.

    No hay un tag estándar de "narrador" entre formatos; se usa
    album_artist como la aproximación más común en audiolibros
    (varios narradores publican con ese campo).
    """
    try:
        audio = mutagen.File(str(file_path), easy=True)
        if audio is None or not audio.tags:
            return None, None, None
        title = next(iter(audio.tags.get("title", [])), None)
        author = next(iter(audio.tags.get("artist", [])), None)
        narrator = next(iter(audio.tags.get("albumartist", [])), None)
        return (title or None), (author or None), (narrator or None)
    except Exception:
        return None, None, None


def _read_duration_ms(file_path: Path) -> Optional[int]:
    try:
        audio = mutagen.File(str(file_path))
        if audio is None or not audio.info or not audio.info.length:
            return None
        return int(audio.info.length * 1000)
    except Exception:
        return None
