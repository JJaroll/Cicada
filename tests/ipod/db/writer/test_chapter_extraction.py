"""Tests para chapter_extraction.py — Fase 5b.

Los archivos con capítulos reales (M4B con átomo Nero chpl, MP3 con frames
ID3v2 CHAP) se construyen aquí byte a byte: no hay audio con copyright de
por medio, y el resultado es exactamente reproducible.
"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from cicada.ipod.db.writer.chapter_extraction import extract_chapters


def _build_atom(fourcc: bytes, body: bytes) -> bytes:
    return struct.pack(">I", 8 + len(body)) + fourcc + body


def _build_nero_chpl_m4b(path: Path, chapters: list[tuple[int, str]]) -> None:
    """chapters: lista de (start_ms, title). Escribe un .m4b mínimo cuyo único
    contenido es moov > udta > chpl — suficiente para el lector de átomos, que
    nunca toca datos de audio."""
    body = bytes([0]) + bytes(4) + bytes([len(chapters)])  # version=0, reserved, count
    for start_ms, title in chapters:
        title_bytes = title.encode("utf-8")
        body += struct.pack(">Q", start_ms * 10_000) + bytes([len(title_bytes)]) + title_bytes
    chpl = _build_atom(b"chpl", body)
    udta = _build_atom(b"udta", chpl)
    moov = _build_atom(b"moov", udta)
    path.write_bytes(moov)


def _build_mp3_with_chap(path: Path, chapters: list[tuple[int, int, str]]) -> None:
    """chapters: lista de (start_ms, end_ms, title). Parte de un MP3 real
    (fixture existente) y le añade frames ID3v2 CHAP con mutagen."""
    import shutil

    from mutagen.id3 import CHAP, TIT2

    base = Path(__file__).resolve().parents[3] / "fixtures" / "audio" / "no_art.mp3"
    shutil.copyfile(base, path)

    from mutagen.mp3 import MP3
    audio = MP3(str(path))
    if audio.tags is None:
        audio.add_tags()
    for i, (start_ms, end_ms, title) in enumerate(chapters):
        audio.tags.add(CHAP(
            element_id=f"chp{i}",
            start_time=start_ms,
            end_time=end_ms,
            sub_frames=[TIT2(encoding=3, text=[title])],
        ))
    audio.save()


def test_extract_chapters_m4b_nero_chpl(tmp_path: Path):
    f = tmp_path / "book.m4b"
    _build_nero_chpl_m4b(f, [(0, "Capitulo 1"), (60000, "Capitulo 2"), (125000, "Capitulo 3")])
    chapters = extract_chapters(str(f))
    assert chapters == [
        {"startpos": 0, "title": "Capitulo 1"},
        {"startpos": 60000, "title": "Capitulo 2"},
        {"startpos": 125000, "title": "Capitulo 3"},
    ]


def test_extract_chapters_m4b_sin_udta_devuelve_none(tmp_path: Path):
    f = tmp_path / "plain.m4b"
    f.write_bytes(_build_atom(b"moov", b"sin-udta-real"))
    assert extract_chapters(str(f)) is None


def test_extract_chapters_mp3_id3_chap(tmp_path: Path):
    f = tmp_path / "episode.mp3"
    _build_mp3_with_chap(f, [(0, 30000, "Intro"), (30000, 90000, "Segmento")])
    chapters = extract_chapters(str(f))
    assert chapters == [
        {"startpos": 0, "title": "Intro"},
        {"startpos": 30000, "title": "Segmento"},
    ]


def test_extract_chapters_mp3_sin_chap_devuelve_none():
    base = Path(__file__).resolve().parents[3] / "fixtures" / "audio" / "no_art.mp3"
    assert extract_chapters(str(base)) is None


def test_extract_chapters_archivo_inexistente_devuelve_none():
    assert extract_chapters("/no/existe/nada.m4b") is None


def test_extract_chapters_extension_no_soportada_devuelve_none(tmp_path: Path):
    f = tmp_path / "cover.jpg"
    f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
    assert extract_chapters(str(f)) is None


def test_extract_chapters_m4b_truncado_no_lanza(tmp_path: Path):
    """Un chpl con el conteo de capítulos declarado pero sin los bytes que
    le siguen no debe reventar — debe devolver None, como cualquier
    archivo ajeno que el usuario podría añadir a su biblioteca."""
    body = bytes([0]) + bytes(4) + bytes([3])  # dice "3 capítulos" y no trae ninguno
    chpl = _build_atom(b"chpl", body)
    udta = _build_atom(b"udta", chpl)
    moov = _build_atom(b"moov", udta)
    f = tmp_path / "truncado.m4b"
    f.write_bytes(moov)
    assert extract_chapters(str(f)) is None
