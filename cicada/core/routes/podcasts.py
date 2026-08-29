"""Router de gestión y descarga de podcasts."""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cicada.podcasts import download_progress
from cicada.podcasts.artwork import embed_artwork
from cicada.podcasts.downloader import DownloadCancelled, episode_cache_dir, download_episode
from cicada.podcasts.feed_parser import fetch_feed
from cicada.podcasts.models import (
    PodcastFeed,
    STATUS_DOWNLOADED,
    STATUS_DOWNLOADING,
    STATUS_NOT_DOWNLOADED,
    STATUS_ON_IPOD,
)
from cicada.podcasts.subscription_store import SubscriptionStore

log = logging.getLogger(__name__)

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
    downloaded_path: str
    last_error: Optional[str] = None


class DownloadProgressSchema(BaseModel):
    guid: str
    state: str
    downloaded_bytes: int = 0
    total_bytes: int = 0
    error: Optional[str] = None
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
                downloaded_path=ep.downloaded_path,
                last_error=ep.last_error,
            )
            for ep in feed.episodes
        ],
    )


@router.post("/subscribe", response_model=FeedSchema)
async def subscribe(req: SubscribeRequest) -> FeedSchema:
    # Suscribe un feed RSS de podcast y guarda episodios.
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
    # Lista todas las suscripciones a podcasts almacenadas.
    store = SubscriptionStore()
    feeds = store.get_feeds()
    return PodcastsResponse(feeds=[_to_schema(f) for f in feeds], count=len(feeds))


def _find_episode(feed_url: str, guid: str):
    store = SubscriptionStore()
    feed = store.get_feed(feed_url)
    if feed is None:
        raise HTTPException(status_code=404, detail="No hay ninguna suscripción a ese feed.")
    episode = next((e for e in feed.episodes if e.guid == guid), None)
    if episode is None:
        raise HTTPException(status_code=404, detail="Ese episodio no existe en el feed suscripto.")
    return store, episode


def _progress_schema(guid: str, persisted_status: str) -> DownloadProgressSchema:
    progress = download_progress.get(guid)
    if progress is None:
        return DownloadProgressSchema(guid=guid, state="idle", status=persisted_status)
    return DownloadProgressSchema(
        guid=guid,
        state=progress.state,
        downloaded_bytes=progress.downloaded_bytes,
        total_bytes=progress.total_bytes,
        error=progress.error,
        status=persisted_status,
    )


async def _run_download(feed_url: str, guid: str, audio_url: str, artwork_url: str) -> None:
    store = SubscriptionStore()
    progress = download_progress.get(guid)
    assert progress is not None

    def on_progress(downloaded: int, total: int) -> None:
        progress.downloaded_bytes = downloaded
        progress.total_bytes = total

    try:
        dest_path = await download_episode(
            audio_url, guid, episode_cache_dir(feed_url), progress_cb=on_progress
        )
        try:
            await embed_artwork(dest_path, artwork_url)
        except Exception as exc:
            log.debug("No se pudo embeber artwork para %s: %s", guid, exc)
        store.set_episode_status(
            guid, status=STATUS_DOWNLOADED, downloaded_path=dest_path, clear_last_error=True
        )
        progress.state = "done"
    except DownloadCancelled as e:
        store.set_episode_status(guid, status=STATUS_NOT_DOWNLOADED, last_error=str(e))
        progress.state = "error"
        progress.error = str(e)
    except Exception as e:
        log.warning("Descarga de episodio %s falló: %s", guid, e)
        store.set_episode_status(guid, status=STATUS_NOT_DOWNLOADED, last_error=str(e))
        progress.state = "error"
        progress.error = str(e)


@router.post(
    "/{feed_url:path}/episodes/{guid}/download",
    response_model=DownloadProgressSchema,
    status_code=202,
)
async def download_episode_endpoint(feed_url: str, guid: str) -> DownloadProgressSchema:
    # Inicia la descarga en segundo plano del episodio.
    store, episode = _find_episode(feed_url, guid)

    if download_progress.is_active(guid):
        return _progress_schema(guid, episode.status)

    feed = store.get_feed(feed_url)
    artwork_url = feed.artwork_url if feed is not None else ""

    store.set_episode_status(guid, status=STATUS_DOWNLOADING, clear_last_error=True)
    download_progress.start(guid)
    asyncio.create_task(_run_download(feed_url, guid, episode.audio_url, artwork_url))

    return _progress_schema(guid, STATUS_DOWNLOADING)


@router.get("/{feed_url:path}/episodes/{guid}/download", response_model=DownloadProgressSchema)
def get_download_progress(feed_url: str, guid: str) -> DownloadProgressSchema:
    # Consulta el estado de descarga del episodio.
    _store, episode = _find_episode(feed_url, guid)
    return _progress_schema(guid, episode.status)


class MarkSyncedRequest(BaseModel):
    guids: List[str]


class MarkSyncedResponse(BaseModel):
    updated: List[str]
    count: int


@router.post("/episodes/mark_synced", response_model=MarkSyncedResponse)
def mark_episodes_synced(req: MarkSyncedRequest) -> MarkSyncedResponse:
    # Marca episodios como sincronizados en el iPod.
    store = SubscriptionStore()
    updated = []
    for guid in req.guids:
        ep = store.get_episode(guid)
        if ep is not None and ep.status == STATUS_DOWNLOADED:
            store.set_episode_status(guid, status=STATUS_ON_IPOD)
            updated.append(guid)
    return MarkSyncedResponse(updated=updated, count=len(updated))
