"""Router de podcasts: suscripción a feeds RSS y listado de lo suscripto.

Independiente del módulo iPod — la persistencia vive en
~/.cicada/podcasts.db, no en el dispositivo. Etapa A: sin descarga de
episodios ni sincronización al iPod todavía (ver docs/VENDORED.md
Paquete 8).
"""
from __future__ import annotations

from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cicada.podcasts.feed_parser import fetch_feed
from cicada.podcasts.models import PodcastFeed
from cicada.podcasts.subscription_store import SubscriptionStore

router = APIRouter(prefix="/api/podcasts")


class SubscribeRequest(BaseModel):
    feed_url: str


class EpisodeSchema(BaseModel):
    guid: str
    title: str
    description: str
    audio_url: str
    pub_date: float
    duration_seconds: int
    size_bytes: int
    episode_number: Optional[int] = None
    season_number: Optional[int] = None
    status: str


class FeedSchema(BaseModel):
    feed_url: str
    title: str
    author: str
    description: str
    artwork_url: str
    category: str
    language: str
    last_refreshed: float
    episode_count: int
    episodes: List[EpisodeSchema]


class PodcastsResponse(BaseModel):
    feeds: List[FeedSchema]
    count: int


def _to_schema(feed: PodcastFeed) -> FeedSchema:
    return FeedSchema(
        feed_url=feed.feed_url,
        title=feed.title,
        author=feed.author,
        description=feed.description,
        artwork_url=feed.artwork_url,
        category=feed.category,
        language=feed.language,
        last_refreshed=feed.last_refreshed,
        episode_count=len(feed.episodes),
        episodes=[
            EpisodeSchema(
                guid=ep.guid,
                title=ep.title,
                description=ep.description,
                audio_url=ep.audio_url,
                pub_date=ep.pub_date,
                duration_seconds=ep.duration_seconds,
                size_bytes=ep.size_bytes,
                episode_number=ep.episode_number,
                season_number=ep.season_number,
                status=ep.status,
            )
            for ep in feed.episodes
        ],
    )


@router.post("/subscribe", response_model=FeedSchema)
async def subscribe(req: SubscribeRequest) -> FeedSchema:
    """Trae un feed RSS y lo guarda como suscripción.

    Idempotente: si el feed ya estaba suscripto, lo refresca (trae
    episodios nuevos, preserva estado local de los ya conocidos) en
    vez de duplicarlo.
    """
    feed_url = req.feed_url.strip()
    if not feed_url:
        raise HTTPException(status_code=400, detail="Falta la URL del feed.")

    store = SubscriptionStore()
    existing = store.get_feed(feed_url)
    try:
        feed = await fetch_feed(feed_url, existing=existing)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar al feed: {e}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"El feed no se pudo leer: {e}")

    store.add_feed(feed)
    return _to_schema(feed)


@router.get("", response_model=PodcastsResponse)
def list_podcasts() -> PodcastsResponse:
    """Lista las suscripciones guardadas (no refresca contra la red)."""
    store = SubscriptionStore()
    feeds = store.get_feeds()
    return PodcastsResponse(feeds=[_to_schema(f) for f in feeds], count=len(feeds))
