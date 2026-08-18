"""extract_embedded_artwork se movió de cicada.core.routes.library a
cicada.shared.artwork para que cicada.ipod (Fase 4, escritor de ArtworkDB)
pueda reusar la misma extracción sin importar de cicada.core ni duplicar
un segundo sistema de carátulas."""
from pathlib import Path

from cicada.shared.artwork import extract_embedded_artwork

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "audio"


def test_extracts_apic_from_mp3():
    data, mime = extract_embedded_artwork(FIXTURES / "with_art.mp3")
    assert data
    assert mime == "image/jpeg"


def test_extracts_covr_from_m4a():
    data, mime = extract_embedded_artwork(FIXTURES / "with_art.m4a")
    assert data
    assert mime == "image/jpeg"


def test_extracts_picture_from_flac():
    data, mime = extract_embedded_artwork(FIXTURES / "with_art.flac")
    assert data
    assert mime == "image/jpeg"


def test_returns_none_when_no_artwork():
    data, mime = extract_embedded_artwork(FIXTURES / "no_art.mp3")
    assert data is None
    assert mime is None


def test_returns_none_for_nonexistent_file():
    data, mime = extract_embedded_artwork(FIXTURES / "does_not_exist.mp3")
    assert data is None
    assert mime is None
