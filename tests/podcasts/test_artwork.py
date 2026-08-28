"""Tests para cicada/podcasts/artwork.py.

Usa httpx.MockTransport para no depender de red en la suite automática.
La verificación contra un feed RSS público real con imagen real se hizo
aparte, manualmente — ver docs/VENDORED.md Paquete 8.
"""
from __future__ import annotations

import io
import shutil
from pathlib import Path

import httpx
import pytest
from PIL import Image

from cicada.podcasts.artwork import embed_artwork, prepare_artwork_bytes

_FIXTURES_AUDIO = Path(__file__).resolve().parents[1] / "fixtures" / "audio"


def _fake_jpeg_bytes(size=(300, 300), color=(200, 50, 50)) -> bytes:
    img = Image.new("RGB", size, color)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    return out.getvalue()


def _fake_png_bytes_rgba(size=(300, 300)) -> bytes:
    img = Image.new("RGBA", size, (10, 20, 30, 128))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _mock_artwork_client(monkeypatch, body: bytes, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=body)

    transport = httpx.MockTransport(handler)

    class _PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("cicada.podcasts.artwork.httpx.AsyncClient", _PatchedAsyncClient)


# ── prepare_artwork_bytes ───────────────────────────────────────────────────

def test_prepare_artwork_bytes_jpeg_valido():
    prepared = prepare_artwork_bytes(_fake_jpeg_bytes())
    assert prepared is not None
    img = Image.open(io.BytesIO(prepared))
    assert img.format == "JPEG"


def test_prepare_artwork_bytes_redimensiona_por_encima_de_1400px():
    prepared = prepare_artwork_bytes(_fake_jpeg_bytes(size=(2000, 2000)))
    assert prepared is not None
    img = Image.open(io.BytesIO(prepared))
    assert max(img.size) == 1400


def test_prepare_artwork_bytes_no_redimensiona_por_debajo_de_1400px():
    prepared = prepare_artwork_bytes(_fake_jpeg_bytes(size=(500, 500)))
    assert prepared is not None
    img = Image.open(io.BytesIO(prepared))
    assert img.size == (500, 500)


def test_prepare_artwork_bytes_convierte_png_con_transparencia():
    prepared = prepare_artwork_bytes(_fake_png_bytes_rgba())
    assert prepared is not None
    img = Image.open(io.BytesIO(prepared))
    assert img.format == "JPEG"
    assert img.mode == "RGB"


def test_prepare_artwork_bytes_datos_invalidos_devuelve_none():
    assert prepare_artwork_bytes(b"esto no es una imagen") is None


def test_prepare_artwork_bytes_vacio_devuelve_none():
    assert prepare_artwork_bytes(b"") is None


# ── embed_artwork ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_embed_artwork_mp3_sin_arte_previo(tmp_path: Path, monkeypatch):
    target = tmp_path / "episode.mp3"
    shutil.copyfile(_FIXTURES_AUDIO / "no_art.mp3", target)
    _mock_artwork_client(monkeypatch, _fake_jpeg_bytes())

    embedded = await embed_artwork(str(target), "https://example.com/art.jpg")
    assert embedded is True

    from mutagen.mp3 import MP3
    audio = MP3(str(target))
    assert any(k.startswith("APIC") for k in audio.tags)


@pytest.mark.asyncio
async def test_embed_artwork_mp3_con_arte_previo_no_lo_sobrescribe(tmp_path: Path, monkeypatch):
    target = tmp_path / "episode.mp3"
    shutil.copyfile(_FIXTURES_AUDIO / "with_art.mp3", target)
    _mock_artwork_client(monkeypatch, _fake_jpeg_bytes())

    embedded = await embed_artwork(str(target), "https://example.com/art.jpg")
    assert embedded is False


@pytest.mark.asyncio
async def test_embed_artwork_m4a_con_arte_previo_no_lo_sobrescribe(tmp_path: Path, monkeypatch):
    # No hay fixture m4a sin arte en el repo; with_art.m4a ya trae covr,
    # así que cubre el camino M4A del check "ya tiene arte, no lo pisa"
    # (el camino M4A "sin arte, sí embebe" comparte la misma rama de
    # código que el caso MP3 ya probado arriba — solo cambia el tag).
    target = tmp_path / "episode.m4a"
    shutil.copyfile(_FIXTURES_AUDIO / "with_art.m4a", target)
    _mock_artwork_client(monkeypatch, _fake_jpeg_bytes())

    embedded = await embed_artwork(str(target), "https://example.com/art.jpg")
    assert embedded is False  # ya tenía covr


@pytest.mark.asyncio
async def test_embed_artwork_sin_url_no_hace_nada(tmp_path: Path):
    target = tmp_path / "episode.mp3"
    shutil.copyfile(_FIXTURES_AUDIO / "no_art.mp3", target)
    embedded = await embed_artwork(str(target), "")
    assert embedded is False


@pytest.mark.asyncio
async def test_embed_artwork_extension_no_soportada(tmp_path: Path, monkeypatch):
    target = tmp_path / "episode.ogg"
    target.write_bytes(b"not really ogg but extension check happens first")
    _mock_artwork_client(monkeypatch, _fake_jpeg_bytes())

    embedded = await embed_artwork(str(target), "https://example.com/art.jpg")
    assert embedded is False


@pytest.mark.asyncio
async def test_embed_artwork_descarga_falla_no_rompe(tmp_path: Path, monkeypatch):
    target = tmp_path / "episode.mp3"
    shutil.copyfile(_FIXTURES_AUDIO / "no_art.mp3", target)
    _mock_artwork_client(monkeypatch, b"not found", status_code=404)

    embedded = await embed_artwork(str(target), "https://example.com/no-existe.jpg")
    assert embedded is False


@pytest.mark.asyncio
async def test_embed_artwork_datos_no_son_imagen_no_rompe(tmp_path: Path, monkeypatch):
    target = tmp_path / "episode.mp3"
    shutil.copyfile(_FIXTURES_AUDIO / "no_art.mp3", target)
    _mock_artwork_client(monkeypatch, b"esto no es una imagen")

    embedded = await embed_artwork(str(target), "https://example.com/art.jpg")
    assert embedded is False
