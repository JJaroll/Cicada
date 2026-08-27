"""Tests para cicada/podcasts/feed_parser.py.

Usa httpx.MockTransport (built-in, sin dependencia extra) para no
depender de red en la suite automática. La verificación contra un feed
RSS real y público se hizo aparte, manualmente, no acá.
"""
from __future__ import annotations

import gzip

import httpx
import pytest

from cicada.podcasts.feed_parser import _decode_feed_bytes, fetch_feed
from cicada.podcasts.models import PodcastFeed

_SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
<channel>
  <title>Podcast de Prueba</title>
  <itunes:author>Autor Test</itunes:author>
  <description>Un podcast de ejemplo</description>
  <language>es</language>
  <itunes:category text="Technology"/>
  <itunes:image href="https://example.com/art.jpg"/>
  <item>
    <title>Episodio 2: El regreso</title>
    <guid>ep-2</guid>
    <pubDate>Mon, 02 Jan 2024 00:00:00 GMT</pubDate>
    <itunes:duration>32:15</itunes:duration>
    <itunes:episode>2</itunes:episode>
    <enclosure url="https://example.com/ep2.mp3" type="audio/mpeg" length="5000000"/>
  </item>
  <item>
    <title>Episodio 1: El comienzo</title>
    <guid>ep-1</guid>
    <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
    <itunes:duration>1:05:00</itunes:duration>
    <itunes:episode>1</itunes:episode>
    <enclosure url="https://example.com/ep1.mp3" type="audio/mpeg" length="4000000"/>
  </item>
  <item>
    <title>Solo notas, sin audio</title>
    <guid>no-audio</guid>
  </item>
</channel>
</rss>
"""


def _mock_client(body: bytes, status_code: int = 200, headers: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=body, headers=headers or {})
    return httpx.MockTransport(handler)


@pytest.fixture
def patch_httpx_client(monkeypatch):
    def _patch(body: bytes, status_code: int = 200, headers: dict | None = None):
        transport = _mock_client(body, status_code, headers)

        class _PatchedAsyncClient(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        monkeypatch.setattr("cicada.podcasts.feed_parser.httpx.AsyncClient", _PatchedAsyncClient)

    return _patch


@pytest.mark.asyncio
async def test_fetch_feed_parsea_metadata_y_episodios(patch_httpx_client):
    patch_httpx_client(_SAMPLE_RSS.encode("utf-8"))

    feed = await fetch_feed("https://example.com/feed.xml")

    assert feed.title == "Podcast de Prueba"
    assert feed.author == "Autor Test"
    assert feed.category == "Technology"
    assert feed.language == "es"
    assert feed.artwork_url == "https://example.com/art.jpg"


@pytest.mark.asyncio
async def test_fetch_feed_omite_entradas_sin_audio(patch_httpx_client):
    patch_httpx_client(_SAMPLE_RSS.encode("utf-8"))

    feed = await fetch_feed("https://example.com/feed.xml")

    guids = {ep.guid for ep in feed.episodes}
    assert guids == {"ep-1", "ep-2"}
    assert "no-audio" not in guids


@pytest.mark.asyncio
async def test_fetch_feed_parsea_duracion_itunes(patch_httpx_client):
    patch_httpx_client(_SAMPLE_RSS.encode("utf-8"))

    feed = await fetch_feed("https://example.com/feed.xml")

    ep1 = next(e for e in feed.episodes if e.guid == "ep-1")
    ep2 = next(e for e in feed.episodes if e.guid == "ep-2")
    assert ep1.duration_seconds == 65 * 60
    assert ep2.duration_seconds == 32 * 60 + 15


@pytest.mark.asyncio
async def test_fetch_feed_sin_entradas_lanza_valueerror(patch_httpx_client):
    patch_httpx_client(b"no es xml valido")

    with pytest.raises(ValueError):
        await fetch_feed("https://example.com/feed.xml")


@pytest.mark.asyncio
async def test_fetch_feed_preserva_estado_local_al_fusionar(patch_httpx_client):
    patch_httpx_client(_SAMPLE_RSS.encode("utf-8"))

    existing = PodcastFeed(feed_url="https://example.com/feed.xml", title="viejo")
    from cicada.podcasts.models import PodcastEpisode
    existing.episodes = [
        PodcastEpisode(guid="ep-1", status="downloaded", downloaded_path="/tmp/ep1.mp3"),
    ]

    feed = await fetch_feed("https://example.com/feed.xml", existing=existing)

    ep1 = next(e for e in feed.episodes if e.guid == "ep-1")
    assert ep1.status == "downloaded"
    assert ep1.downloaded_path == "/tmp/ep1.mp3"
    assert ep1.title == "Episodio 1: El comienzo"  # metadata RSS actualizada


def test_decode_feed_bytes_gzip_valido():
    raw = b"contenido de prueba"
    compressed = gzip.compress(raw)
    assert _decode_feed_bytes(compressed, "gzip") == raw


def test_decode_feed_bytes_gzip_invalido_hace_fallback():
    raw = b"no esta comprimido en realidad"
    assert _decode_feed_bytes(raw, "gzip") == raw


def test_decode_feed_bytes_sin_encoding_devuelve_igual():
    raw = b"<rss>...</rss>"
    assert _decode_feed_bytes(raw, "") == raw
