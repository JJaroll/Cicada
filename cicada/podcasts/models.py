"""Modelos de datos para feeds y episodios de podcasts."""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

STATUS_NOT_DOWNLOADED = "not_downloaded"
STATUS_DOWNLOADING = "downloading"
STATUS_DOWNLOADED = "downloaded"
STATUS_ON_IPOD = "on_ipod"

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp")


def normalize_artwork_url(url: str) -> str:
    # Normaliza URLs de carátulas con extensiones malformadas.
    raw = (url or "").strip()
    if not raw or "?" not in raw:
        return raw

    parsed = urlsplit(raw)
    query = parsed.query.strip().lower()
    if not query:
        return raw

    normalized_ext = query if query.startswith(".") else f".{query}"
    if normalized_ext not in _IMAGE_EXTENSIONS:
        return raw

    if parsed.path.lower().endswith(_IMAGE_EXTENSIONS):
        return raw

    return urlunsplit((parsed.scheme, parsed.netloc, f"{parsed.path}{normalized_ext}", "", parsed.fragment))


@dataclass
class PodcastEpisode:
    """Un episodio dentro de un feed."""

    guid: str
    title: str = ""
    description: str = ""
    audio_url: str = ""
    pub_date: float = 0.0
    duration_seconds: int = 0
    size_bytes: int = 0
    episode_number: int | None = None
    season_number: int | None = None

    status: str = STATUS_NOT_DOWNLOADED
    downloaded_path: str = ""
    last_error: str | None = None
    """Mensaje del último intento de descarga fallido. Persiste incluso
    después de que status vuelva a not_downloaded (permite reintentar sin
    perder por qué falló el intento anterior); se limpia recién cuando una
    nueva descarga arranca."""

    def to_dict(self) -> dict:
        return {
            "guid": self.guid,
            "title": self.title,
            "description": self.description,
            "audio_url": self.audio_url,
            "pub_date": self.pub_date,
            "duration_seconds": self.duration_seconds,
            "size_bytes": self.size_bytes,
            "episode_number": self.episode_number,
            "season_number": self.season_number,
            "status": self.status,
            "downloaded_path": self.downloaded_path,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, d: dict) -> PodcastEpisode:
        return cls(
            guid=d["guid"],
            title=d.get("title", ""),
            description=d.get("description", ""),
            audio_url=d.get("audio_url", ""),
            pub_date=d.get("pub_date", 0.0),
            duration_seconds=d.get("duration_seconds", 0),
            size_bytes=d.get("size_bytes", 0),
            episode_number=d.get("episode_number"),
            season_number=d.get("season_number"),
            status=d.get("status", STATUS_NOT_DOWNLOADED),
            downloaded_path=d.get("downloaded_path", ""),
            last_error=d.get("last_error"),
        )


@dataclass
class PodcastFeed:
    """Un podcast (programa) suscripto, con sus episodios."""

    feed_url: str
    title: str = ""
    author: str = ""
    description: str = ""
    artwork_url: str = ""
    category: str = ""
    language: str = ""
    last_refreshed: float = 0.0

    episodes: list[PodcastEpisode] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "feed_url": self.feed_url,
            "title": self.title,
            "author": self.author,
            "description": self.description,
            "artwork_url": self.artwork_url,
            "category": self.category,
            "language": self.language,
            "last_refreshed": self.last_refreshed,
            "episodes": [ep.to_dict() for ep in self.episodes],
        }

    @classmethod
    def from_dict(cls, d: dict) -> PodcastFeed:
        episodes = [PodcastEpisode.from_dict(e) for e in d.get("episodes", [])]
        return cls(
            feed_url=d["feed_url"],
            title=d.get("title", ""),
            author=d.get("author", ""),
            description=d.get("description", ""),
            artwork_url=normalize_artwork_url(d.get("artwork_url", "")),
            category=d.get("category", ""),
            language=d.get("language", ""),
            last_refreshed=d.get("last_refreshed", 0.0),
            episodes=episodes,
        )
