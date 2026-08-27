"""Tests para cicada/podcasts/downloader.py.

Usa httpx.MockTransport para no depender de red en la suite automática.
La descarga real contra un episodio público se hizo aparte, manualmente.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from cicada.podcasts.downloader import (
    DownloadCancelled,
    download_episode,
    episode_cache_dir,
)


def _mock_download_client(monkeypatch, body: bytes, status_code: int = 200, headers: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=body, headers=headers or {})

    transport = httpx.MockTransport(handler)

    class _PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("cicada.podcasts.downloader.httpx.AsyncClient", _PatchedAsyncClient)


def test_episode_cache_dir_es_determinista_por_feed_url():
    a = episode_cache_dir("https://example.com/feed.xml")
    b = episode_cache_dir("https://example.com/feed.xml")
    c = episode_cache_dir("https://otro.com/feed.xml")
    assert a == b
    assert a != c


@pytest.mark.asyncio
async def test_download_episode_escribe_archivo_completo(tmp_path: Path, monkeypatch):
    audio_bytes = b"fake mp3 bytes " * 1000
    _mock_download_client(monkeypatch, audio_bytes, headers={"Content-Type": "audio/mpeg"})

    dest_dir = tmp_path / "cache"
    result_path = await download_episode("https://example.com/ep1.mp3", "guid-1", dest_dir)

    result = Path(result_path)
    assert result.exists()
    assert result.read_bytes() == audio_bytes
    assert result.suffix == ".mp3"


@pytest.mark.asyncio
async def test_download_episode_no_deja_archivo_temporal_huerfano_en_exito(tmp_path: Path, monkeypatch):
    _mock_download_client(monkeypatch, b"contenido", headers={"Content-Type": "audio/mpeg"})

    dest_dir = tmp_path / "cache"
    await download_episode("https://example.com/ep1.mp3", "guid-1", dest_dir)

    leftovers = list(dest_dir.glob(".dl-*"))
    assert leftovers == []


@pytest.mark.asyncio
async def test_download_episode_http_error_no_deja_temporal_huerfano(tmp_path: Path, monkeypatch):
    _mock_download_client(monkeypatch, b"not found", status_code=404)

    dest_dir = tmp_path / "cache"
    with pytest.raises(httpx.HTTPStatusError):
        await download_episode("https://example.com/no-existe.mp3", "guid-404", dest_dir)

    assert not dest_dir.exists() or list(dest_dir.glob(".dl-*")) == []
    assert not dest_dir.exists() or list(dest_dir.glob("guid-404*")) == []


@pytest.mark.asyncio
async def test_download_episode_cancelada_no_deja_temporal_huerfano(tmp_path: Path, monkeypatch):
    # Cuerpo grande para asegurar que haya varios chunks y de tiempo a cancelar
    # a mitad, no en el primer chunk.
    audio_bytes = b"x" * (_chunk_multiple := 64 * 1024 * 3)
    _mock_download_client(monkeypatch, audio_bytes, headers={"Content-Type": "audio/mpeg"})

    dest_dir = tmp_path / "cache"
    calls = {"n": 0}

    def is_cancelled():
        calls["n"] += 1
        return calls["n"] > 1  # cancela después del primer chunk

    with pytest.raises(DownloadCancelled):
        await download_episode(
            "https://example.com/ep-grande.mp3", "guid-cancel", dest_dir, is_cancelled=is_cancelled
        )

    assert not dest_dir.exists() or list(dest_dir.glob(".dl-*")) == []
    assert not dest_dir.exists() or list(dest_dir.glob("guid-cancel*")) == []
