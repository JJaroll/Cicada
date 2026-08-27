"""Tests para POST /api/podcasts/episodes/mark_synced."""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from cicada.core.main import app
from cicada.podcasts.models import PodcastEpisode, PodcastFeed
from cicada.podcasts.subscription_store import SubscriptionStore


@pytest.fixture
def store(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "podcasts.db"
    monkeypatch.setattr(
        "cicada.podcasts.subscription_store.default_podcasts_db_path", lambda: db_path
    )
    s = SubscriptionStore(db_path=db_path)
    feed = PodcastFeed(
        feed_url="https://example.com/feed.xml",
        title="Show",
        episodes=[
            PodcastEpisode(guid="ep-downloaded", status="downloaded", downloaded_path="/tmp/ep1.mp3"),
            PodcastEpisode(guid="ep-not-downloaded", status="not_downloaded"),
            PodcastEpisode(guid="ep-on-ipod", status="on_ipod", downloaded_path="/tmp/ep3.mp3"),
        ],
    )
    s.add_feed(feed)
    return s


@pytest.fixture
def async_client(store):
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_mark_synced_actualiza_episodio_downloaded(async_client: httpx.AsyncClient, store):
    res = await async_client.post("/api/podcasts/episodes/mark_synced", json={"guids": ["ep-downloaded"]})
    assert res.status_code == 200
    body = res.json()
    assert body["updated"] == ["ep-downloaded"]
    assert body["count"] == 1

    ep = store.get_episode("ep-downloaded")
    assert ep.status == "on_ipod"


@pytest.mark.asyncio
async def test_mark_synced_ignora_episodio_no_downloaded(async_client: httpx.AsyncClient, store):
    res = await async_client.post("/api/podcasts/episodes/mark_synced", json={"guids": ["ep-not-downloaded"]})
    assert res.status_code == 200
    body = res.json()
    assert body["updated"] == []
    assert body["count"] == 0

    ep = store.get_episode("ep-not-downloaded")
    assert ep.status == "not_downloaded"  # sin cambios


@pytest.mark.asyncio
async def test_mark_synced_ignora_episodio_ya_on_ipod(async_client: httpx.AsyncClient, store):
    res = await async_client.post("/api/podcasts/episodes/mark_synced", json={"guids": ["ep-on-ipod"]})
    body = res.json()
    assert body["updated"] == []  # ya estaba on_ipod, no re-procesado (no rompe, tampoco duplica)


@pytest.mark.asyncio
async def test_mark_synced_ignora_guid_inexistente_sin_fallar(async_client: httpx.AsyncClient, store):
    res = await async_client.post("/api/podcasts/episodes/mark_synced", json={"guids": ["no-existe"]})
    assert res.status_code == 200
    assert res.json() == {"updated": [], "count": 0}


@pytest.mark.asyncio
async def test_mark_synced_lista_mixta_procesa_lo_valido_ignora_el_resto(async_client: httpx.AsyncClient, store):
    res = await async_client.post(
        "/api/podcasts/episodes/mark_synced",
        json={"guids": ["ep-downloaded", "ep-not-downloaded", "no-existe"]},
    )
    body = res.json()
    assert body["updated"] == ["ep-downloaded"]
    assert body["count"] == 1


@pytest.mark.asyncio
async def test_mark_synced_lista_vacia_no_hace_nada(async_client: httpx.AsyncClient, store):
    res = await async_client.post("/api/podcasts/episodes/mark_synced", json={"guids": []})
    assert res.status_code == 200
    assert res.json() == {"updated": [], "count": 0}
