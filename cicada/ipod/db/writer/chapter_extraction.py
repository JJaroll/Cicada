"""Extrae marcadores de capítulo embebidos en un archivo local de audio.

Vendorizado (parcial) desde ``src/iopenpod/podcasts/downloader.py`` @
``c66a4bdb`` — ver docs/VENDORED.md Paquete 8. El paquete `podcasts/` de
origen es gestión de feeds RSS (fuera de alcance); esta es la única pieza
desacoplada de feeds: lee capítulos de un archivo local ya existente.

Soporta:
  - MP4/M4A/M4B/M4V/MOV: átomo Nero ``chpl`` bajo ``moov.udta.chpl``.
  - MP3: frames ID3v2 ``CHAP``.

No soportado a propósito (sin caso de uso hoy, ver VENDORED.md): pista de
capítulos QuickTime sin átomo Nero, que en origen requiere ``ffprobe`` —
Cicada no tiene esa dependencia.

El resultado es una lista cruda de ``{"startpos": ms, "title": str}``
ordenada por posición; la validación/normalización final (orden estricto,
límite de cantidad, títulos sospechosos) ya la hace
``mhod_writer._normalized_chapters_for_track`` al escribir, así que no se
duplica aquí.
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import BinaryIO

_MAX_CHAPTER_COUNT = 500
_MP4_CONTAINER_ATOMS = {b"moov", b"udta"}

_MP4_CHAPTER_EXTS = {".m4a", ".m4b", ".m4v", ".mov", ".mp4", ".aac"}


def extract_chapters(file_path: str) -> list[dict] | None:
    """Extrae capítulos de un archivo de audio/video local, si los tiene.

    Devuelve ``[{"startpos": ms, "title": str}, ...]`` ordenado por
    posición, o ``None`` si no hay capítulos o el archivo no es legible.
    """
    if not file_path or not Path(file_path).is_file():
        return None
    ext = Path(file_path).suffix.lower()
    try:
        if ext in _MP4_CHAPTER_EXTS:
            return _read_nero_chapters(file_path)
        if ext == ".mp3":
            return _chapters_from_mp3(file_path)
    except Exception:
        return None
    return None


def _chapters_from_mp3(file_path: str) -> list[dict] | None:
    """Frames ID3v2 CHAP (mutagen puro, sin dependencias nuevas)."""
    from mutagen.id3 import ID3

    try:
        tags = ID3(file_path)
    except Exception:
        return None

    chapters = []
    for key, frame in tags.items():
        if not key.startswith("CHAP"):
            continue
        start_ms = getattr(frame, "start_time", None)
        if start_ms is None:
            continue
        # mutagen >=1.4x guarda sub_frames en un ID3Tags dict-like
        # {frame_id: frame} (no es dict real: isinstance(..., dict) da
        # False), no una lista como en la versión contra la que se
        # escribió el código de origen — iterar el objeto tal cual da las
        # claves (strings), no los frames, y la búsqueda de título fallaba
        # en silencio.
        sub_frames = getattr(frame, "sub_frames", None) or []
        if hasattr(sub_frames, "values"):
            sub_frames = sub_frames.values()
        title = ""
        for sub in sub_frames:
            if hasattr(sub, "text") and sub.text:
                title = str(sub.text[0])
                break
        if not title:
            title = f"Chapter {len(chapters) + 1}"
        chapters.append({"startpos": int(start_ms), "title": title})

    if not chapters:
        return None
    chapters.sort(key=lambda c: c["startpos"])
    return chapters


def _read_nero_chapters(file_path: str) -> list[dict] | None:
    """Átomo Nero ``chpl`` (moov.udta.chpl), bytes crudos — mutagen no lo expone."""
    with open(file_path, "rb") as f:
        f.seek(0, 2)
        end = f.tell()
        body_range = _find_mp4_atom_range(f, start=0, end=end, path=(b"moov", b"udta", b"chpl"))
        if body_range is None:
            return None

        body_start, _body_end = body_range
        f.seek(body_start)
        header = f.read(5)
        if len(header) != 5:
            return None

        version = header[0]
        if version == 1:
            count_data = f.read(4)
            if len(count_data) != 4:
                return None
            count = struct.unpack(">I", count_data)[0]
        else:
            count_data = f.read(1)
            if len(count_data) != 1:
                return None
            count = count_data[0]

        if count == 0 or count > _MAX_CHAPTER_COUNT:
            return None

        chapters = []
        for _ in range(count):
            entry = f.read(9)
            if len(entry) != 9:
                return None
            ms = struct.unpack(">Q", entry[:8])[0] // 10_000
            title_data = f.read(entry[8])
            if len(title_data) != entry[8]:
                return None
            chapters.append({
                "startpos": int(ms),
                "title": title_data.decode("utf-8", errors="replace"),
            })

    if not chapters:
        return None
    chapters.sort(key=lambda c: c["startpos"])
    return chapters


def _find_mp4_atom_range(
    media_file: BinaryIO, *, start: int, end: int, path: tuple[bytes, ...],
) -> tuple[int, int] | None:
    """Rango de bytes de un átomo MP4 anidado, sin cargar datos de medio."""
    if not path:
        return start, end

    needle = path[0]
    for atom_type, body_start, body_end in _iter_mp4_file_atoms(media_file, start, end):
        if atom_type != needle:
            continue
        if len(path) == 1:
            return body_start, body_end
        if atom_type not in _MP4_CONTAINER_ATOMS:
            return None
        return _find_mp4_atom_range(media_file, start=body_start, end=body_end, path=path[1:])
    return None


def _iter_mp4_file_atoms(media_file: BinaryIO, start: int, end: int):
    """Recorre átomos MP4 leyendo solo sus headers."""
    pos = start
    while pos + 8 <= end:
        media_file.seek(pos)
        header = media_file.read(8)
        if len(header) != 8:
            return
        size = struct.unpack(">I", header[:4])[0]
        atom_type = header[4:]
        header_size = 8

        if size == 1:
            extended_size = media_file.read(8)
            if len(extended_size) != 8:
                return
            size = struct.unpack(">Q", extended_size)[0]
            header_size = 16
        elif size == 0:
            size = end - pos

        if size < header_size or pos + size > end:
            return

        yield atom_type, pos + header_size, pos + size
        pos += size
