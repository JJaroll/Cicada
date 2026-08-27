"""Tests para cicada/core/audiobook_scanner.py."""
from __future__ import annotations

import struct
from pathlib import Path

from cicada.core.audiobook_scanner import (
    _MAX_DEPTH,
    _MAX_FILES,
    scan_audiobook_folder,
)


def _build_atom(fourcc: bytes, body: bytes) -> bytes:
    return struct.pack(">I", 8 + len(body)) + fourcc + body


def _build_nero_chpl_m4b(path: Path, chapters: list[tuple[int, str]]) -> None:
    body = bytes([0]) + bytes(4) + bytes([len(chapters)])
    for start_ms, title in chapters:
        title_bytes = title.encode("utf-8")
        body += struct.pack(">Q", start_ms * 10_000) + bytes([len(title_bytes)]) + title_bytes
    chpl = _build_atom(b"chpl", body)
    udta = _build_atom(b"udta", chpl)
    moov = _build_atom(b"moov", udta)
    path.write_bytes(moov)


def test_scan_carpeta_inexistente_devuelve_vacio(tmp_path: Path):
    result = scan_audiobook_folder(str(tmp_path / "no-existe"))
    assert result == {"audiobooks": [], "count": 0, "truncated": False}


def test_scan_filtra_por_extension(tmp_path: Path):
    (tmp_path / "libro.m4b").write_bytes(b"")
    (tmp_path / "cancion.mp3").write_bytes(b"")
    (tmp_path / "notas.txt").write_text("no es audio")
    (tmp_path / "video.mov").write_bytes(b"")

    result = scan_audiobook_folder(str(tmp_path))
    paths = {Path(ab["path"]).name for ab in result["audiobooks"]}
    assert paths == {"libro.m4b", "cancion.mp3"}
    assert result["truncated"] is False


def test_scan_lee_capitulos_de_m4b_con_chpl(tmp_path: Path):
    f = tmp_path / "libro.m4b"
    _build_nero_chpl_m4b(f, [(0, "Cap 1"), (60000, "Cap 2"), (120000, "Cap 3")])

    result = scan_audiobook_folder(str(tmp_path))
    assert result["count"] == 1
    ab = result["audiobooks"][0]
    assert ab["chapter_count"] == 3
    assert ab["filetype"] == "m4b"


def test_scan_sin_capitulos_da_chapter_count_none(tmp_path: Path):
    f = tmp_path / "libro.m4b"
    f.write_bytes(_build_atom(b"moov", b"sin-udta"))

    result = scan_audiobook_folder(str(tmp_path))
    assert result["audiobooks"][0]["chapter_count"] is None


def test_scan_usa_nombre_de_archivo_como_titulo_fallback(tmp_path: Path):
    f = tmp_path / "El Mundo y sus Demonios.m4b"
    f.write_bytes(b"")

    result = scan_audiobook_folder(str(tmp_path))
    assert result["audiobooks"][0]["title"] == "El Mundo y sus Demonios"


def test_scan_no_sigue_symlinks(tmp_path: Path):
    real_dir = tmp_path / "afuera"
    real_dir.mkdir()
    (real_dir / "fuera.m4b").write_bytes(b"")

    root = tmp_path / "raiz"
    root.mkdir()
    (root / "adentro.m4b").write_bytes(b"")
    (root / "link_ciclico").symlink_to(real_dir)

    result = scan_audiobook_folder(str(root))
    paths = {Path(ab["path"]).name for ab in result["audiobooks"]}
    assert paths == {"adentro.m4b"}


def test_scan_corta_por_profundidad_maxima(tmp_path: Path):
    deep = tmp_path
    for i in range(_MAX_DEPTH + 3):
        deep = deep / f"nivel{i}"
        deep.mkdir()
        (deep / f"libro{i}.m4b").write_bytes(b"")

    result = scan_audiobook_folder(str(tmp_path))
    depths_found = set()
    for ab in result["audiobooks"]:
        rel = Path(ab["path"]).relative_to(Path(tmp_path).resolve())
        depths_found.add(len(rel.parts) - 1)

    assert max(depths_found) == _MAX_DEPTH
    assert (_MAX_DEPTH + 1) not in depths_found
    assert (_MAX_DEPTH + 2) not in depths_found


def test_scan_corta_por_cantidad_maxima_de_archivos(tmp_path: Path):
    for i in range(_MAX_FILES + 5):
        (tmp_path / f"libro{i:05d}.m4b").write_bytes(b"")

    result = scan_audiobook_folder(str(tmp_path))
    assert result["count"] == _MAX_FILES
    assert result["truncated"] is True
