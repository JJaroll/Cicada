"""Parser de feeds RSS/Atom de podcasts."""
from __future__ import annotations

import calendar
import gzip
import logging
import time
import zlib

import feedparser
import httpx

from .models import PodcastEpisode, PodcastFeed, normalize_artwork_url

log = logging.getLogger(__name__)

_TIMEOUT = 20.0


async def _fetch_feed_bytes(url: str) -> bytes:
    """Trae los bytes crudos del feed sin confiar en el content-encoding
    anunciado por el servidor.

    Algunos CDNs de podcasts anuncian gzip pero devuelven XML plano, o
    bytes comprimidos corruptos. Pedimos ``identity`` explícitamente y
    decodificamos nosotros mismos solo si el header lo indica, con
    fallback a los bytes crudos si la decodificación falla.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
        resp = await client.get(
            url,
            headers={
                "User-Agent": "Cicada (Podcast Manager)",
                "Accept": (
                    "application/rss+xml, application/atom+xml, "
                    "application/xml, text/xml, */*;q=0.8"
                ),
                "Accept-Encoding": "identity",
            },
        )
        resp.raise_for_status()
        return _decode_feed_bytes(resp.content, resp.headers.get("Content-Encoding", ""))


def _decode_feed_bytes(data: bytes, content_encoding: str) -> bytes:
    encoding = (content_encoding or "").lower()
    if not data:
        return data

    if "gzip" in encoding:
        try:
            return gzip.decompress(data)
        except (OSError, zlib.error) as exc:
            log.debug("Ignorando content-encoding gzip inválido en feed de podcast: %s", exc)
            return data

    if "deflate" in encoding:
        try:
            return zlib.decompress(data)
        except zlib.error as exc:
            log.debug("Ignorando content-encoding deflate inválido en feed de podcast: %s", exc)
            return data

    return data


async def fetch_feed(url: str, existing: PodcastFeed | None = None) -> PodcastFeed:
    """Trae y parsea un feed RSS/Atom de podcast.

    Si se pasa `existing`, los episodios nuevos se fusionan preservando
    estado local (descarga) de los episodios ya conocidos.

    Raises:
        httpx.HTTPError: en errores de red.
        ValueError: si el feed no trae entradas o no se puede parsear.
    """
    parsed = feedparser.parse(await _fetch_feed_bytes(url))

    if parsed.bozo and not parsed.entries:
        raise ValueError(f"Error de parseo del feed: {parsed.bozo_exception}")

    feed_info = parsed.feed

    new_episodes = []
    for entry in parsed.entries:
        ep = _parse_episode(entry)
        if ep is not None:
            new_episodes.append(ep)

    if existing is not None:
        return _merge_feed(existing, feed_info, new_episodes)

    return PodcastFeed(
        feed_url=url,
        title=_get_text(feed_info, "title", "Podcast sin título"),
        author=(_get_text(feed_info, "author") or _get_itunes(feed_info, "author", "")),
        description=(_get_text(feed_info, "subtitle") or _get_text(feed_info, "summary", "")),
        artwork_url=normalize_artwork_url(_get_artwork_url(feed_info)),
        category=_get_itunes_category(feed_info),
        language=_get_text(feed_info, "language", ""),
        last_refreshed=time.time(),
        episodes=new_episodes,
    )


def _merge_feed(existing: PodcastFeed, feed_info, new_episodes: list[PodcastEpisode]) -> PodcastFeed:
    """Fusiona episodios nuevos en un feed existente, preservando estado local
    (descarga) de los episodios ya conocidos, identificados por guid."""
    existing_by_guid = {ep.guid: ep for ep in existing.episodes}

    merged: list[PodcastEpisode] = []
    for ep in new_episodes:
        old = existing_by_guid.pop(ep.guid, None)
        if old is not None:
            ep.status = old.status
            ep.downloaded_path = old.downloaded_path
        merged.append(ep)

    for old_ep in existing_by_guid.values():
        if old_ep.downloaded_path:
            merged.append(old_ep)

    existing.title = _get_text(feed_info, "title") or existing.title
    existing.author = (
        _get_text(feed_info, "author") or _get_itunes(feed_info, "author", "") or existing.author
    )
    existing.description = (
        _get_text(feed_info, "subtitle") or _get_text(feed_info, "summary", "") or existing.description
    )
    existing.artwork_url = normalize_artwork_url(_get_artwork_url(feed_info)) or existing.artwork_url
    existing.category = _get_itunes_category(feed_info) or existing.category
    existing.language = _get_text(feed_info, "language", "") or existing.language
    existing.last_refreshed = time.time()
    existing.episodes = merged
    return existing


def _parse_episode(entry) -> PodcastEpisode | None:
    audio_url = ""
    size_bytes = 0

    for link in entry.get("links", []):
        if link.get("rel") == "enclosure":
            href = link.get("href", "")
            mime = link.get("type", "")
            if href and ("audio" in mime or _looks_like_audio(href)):
                audio_url = href
                try:
                    size_bytes = int(link.get("length", 0))
                except (ValueError, TypeError):
                    size_bytes = 0
                break

    if not audio_url:
        for enc in entry.get("enclosures", []):
            href = enc.get("href", "")
            mime = enc.get("type", "")
            if href and ("audio" in mime or _looks_like_audio(href)):
                audio_url = href
                try:
                    size_bytes = int(enc.get("length", 0))
                except (ValueError, TypeError):
                    size_bytes = 0
                break

    if not audio_url:
        return None

    guid = entry.get("id") or audio_url

    pub_date = 0.0
    if entry.get("published_parsed"):
        try:
            pub_date = calendar.timegm(entry.published_parsed)
        except (TypeError, OverflowError, ValueError):
            pass

    duration = _parse_duration(_get_itunes(entry, "duration", ""))

    ep_num = None
    season_num = None
    try:
        ep_num = int(_get_itunes(entry, "episode", "0")) or None
    except (ValueError, TypeError):
        pass
    try:
        season_num = int(_get_itunes(entry, "season", "0")) or None
    except (ValueError, TypeError):
        pass

    return PodcastEpisode(
        guid=guid,
        title=_get_text(entry, "title", "Episodio sin título"),
        description=(_get_text(entry, "subtitle") or _get_text(entry, "summary", "")),
        audio_url=audio_url,
        pub_date=pub_date,
        duration_seconds=duration,
        size_bytes=size_bytes,
        episode_number=ep_num,
        season_number=season_num,
    )

def _get_text(obj, attr: str, default: str = "") -> str:
    val = _get_attr_or_key(obj, attr)
    return str(val).strip() if val else default


def _get_itunes(obj, key: str, default: str = "") -> str:
    val = _get_attr_or_key(obj, f"itunes_{key}")
    return str(val).strip() if val else default


def _get_attr_or_key(obj, name: str):
    if hasattr(obj, "get"):
        try:
            value = obj.get(name)
            if value:
                return value
        except Exception:
            pass
    return getattr(obj, name, None)


def _get_artwork_url(feed_info) -> str:
    img = feed_info.get("image") if hasattr(feed_info, "get") else getattr(feed_info, "image", None)
    if img:
        href = img.get("href", "") if isinstance(img, dict) else getattr(img, "href", "")
        if href:
            return href

    itunes_img = feed_info.get("itunes_image") if hasattr(feed_info, "get") else None
    if itunes_img:
        href = itunes_img.get("href", "") if isinstance(itunes_img, dict) else ""
        if href:
            return href

    return ""


def _get_itunes_category(feed_info) -> str:
    tags = feed_info.get("tags") if hasattr(feed_info, "get") else getattr(feed_info, "tags", None)
    if tags:
        for tag in tags:
            term = tag.get("term", "") if isinstance(tag, dict) else getattr(tag, "term", "")
            if term:
                return term
    return ""


_AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".flac", ".wma"}


def _looks_like_audio(url: str) -> bool:
    path = url.split("?")[0].lower()
    return any(path.endswith(ext) for ext in _AUDIO_EXTS)


def _parse_duration(raw: str) -> int:
    """Parsea itunes:duration: "3600", "60:00", "1:00:00"."""
    if not raw:
        return 0

    if raw.isdigit():
        return int(raw)

    parts = raw.split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return 0

    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0
