"""Persistencia y almacenamiento de suscripciones a podcasts en SQLite."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from .models import PodcastEpisode, PodcastFeed


def default_podcasts_db_path() -> Path:
    """Ruta por defecto de la base de datos local (~/.cicada/podcasts.db o $CICADA_HOME/podcasts.db)."""
    base = Path(os.environ.get("CICADA_HOME") or (Path.home() / ".cicada"))
    return base / "podcasts.db"


class SubscriptionStore:
    """Acceso y persistencia de suscripciones a podcasts en SQLite."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path is not None else default_podcasts_db_path()
        self._init_db()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS feeds (
                    feed_url TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    author TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    artwork_url TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT '',
                    language TEXT NOT NULL DEFAULT '',
                    last_refreshed REAL NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS episodes (
                    guid TEXT PRIMARY KEY,
                    feed_url TEXT NOT NULL REFERENCES feeds(feed_url) ON DELETE CASCADE,
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    audio_url TEXT NOT NULL DEFAULT '',
                    pub_date REAL NOT NULL DEFAULT 0,
                    duration_seconds INTEGER NOT NULL DEFAULT 0,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    episode_number INTEGER,
                    season_number INTEGER,
                    status TEXT NOT NULL DEFAULT 'not_downloaded',
                    downloaded_path TEXT NOT NULL DEFAULT '',
                    last_error TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_episodes_feed_url ON episodes(feed_url);
                """
            )
            conn.commit()

    def get_feeds(self) -> list[PodcastFeed]:
        # Devuelve la lista de feeds de podcasts suscritos.
        with self._connection() as conn:
            feed_rows = conn.execute("SELECT * FROM feeds ORDER BY title COLLATE NOCASE").fetchall()
            return [self._row_to_feed(conn, row) for row in feed_rows]

    def get_feed(self, feed_url: str) -> PodcastFeed | None:
        # Obtiene un feed específico por su URL.
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM feeds WHERE feed_url = ?", (feed_url,)).fetchone()
            if row is None:
                return None
            return self._row_to_feed(conn, row)

    def _row_to_feed(self, conn: sqlite3.Connection, row: sqlite3.Row) -> PodcastFeed:
        ep_rows = conn.execute(
            "SELECT * FROM episodes WHERE feed_url = ? ORDER BY pub_date DESC",
            (row["feed_url"],),
        ).fetchall()
        episodes = [self._row_to_episode(r) for r in ep_rows]
        return PodcastFeed(
            feed_url=row["feed_url"],
            title=row["title"],
            author=row["author"],
            description=row["description"],
            artwork_url=row["artwork_url"],
            category=row["category"],
            language=row["language"],
            last_refreshed=row["last_refreshed"],
            episodes=episodes,
        )

    @staticmethod
    def _row_to_episode(row: sqlite3.Row) -> PodcastEpisode:
        return PodcastEpisode(
            guid=row["guid"],
            title=row["title"],
            description=row["description"],
            audio_url=row["audio_url"],
            pub_date=row["pub_date"],
            duration_seconds=row["duration_seconds"],
            size_bytes=row["size_bytes"],
            episode_number=row["episode_number"],
            season_number=row["season_number"],
            status=row["status"],
            downloaded_path=row["downloaded_path"],
            last_error=row["last_error"],
        )

    def get_episode(self, guid: str) -> PodcastEpisode | None:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM episodes WHERE guid = ?", (guid,)).fetchone()
            return self._row_to_episode(row) if row is not None else None

    def add_feed(self, feed: PodcastFeed) -> None:
        # Guarda o actualiza un feed y sus episodios.
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO feeds (feed_url, title, author, description, artwork_url,
                                    category, language, last_refreshed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(feed_url) DO UPDATE SET
                    title=excluded.title, author=excluded.author,
                    description=excluded.description, artwork_url=excluded.artwork_url,
                    category=excluded.category, language=excluded.language,
                    last_refreshed=excluded.last_refreshed
                """,
                (
                    feed.feed_url, feed.title, feed.author, feed.description,
                    feed.artwork_url, feed.category, feed.language, feed.last_refreshed,
                ),
            )
            for ep in feed.episodes:
                conn.execute(
                    """
                    INSERT INTO episodes (guid, feed_url, title, description, audio_url,
                                           pub_date, duration_seconds, size_bytes,
                                           episode_number, season_number, status, downloaded_path,
                                           last_error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(guid) DO UPDATE SET
                        feed_url=excluded.feed_url, title=excluded.title,
                        description=excluded.description, audio_url=excluded.audio_url,
                        pub_date=excluded.pub_date, duration_seconds=excluded.duration_seconds,
                        size_bytes=excluded.size_bytes, episode_number=excluded.episode_number,
                        season_number=excluded.season_number, status=excluded.status,
                        downloaded_path=excluded.downloaded_path, last_error=excluded.last_error
                    """,
                    (
                        ep.guid, feed.feed_url, ep.title, ep.description, ep.audio_url,
                        ep.pub_date, ep.duration_seconds, ep.size_bytes,
                        ep.episode_number, ep.season_number, ep.status, ep.downloaded_path,
                        ep.last_error,
                    ),
                )
            conn.commit()

    def update_feed(self, feed: PodcastFeed) -> None:
        """Alias de add_feed — el upsert ya cubre "actualizar existente"."""
        self.add_feed(feed)

    def set_episode_status(
        self,
        guid: str,
        *,
        status: str,
        downloaded_path: str | None = None,
        last_error: str | None = None,
        clear_last_error: bool = False,
    ) -> None:
        # Actualiza el estado de descarga de un episodio.
        with self._connection() as conn:
            if downloaded_path is not None and last_error is not None:
                conn.execute(
                    "UPDATE episodes SET status = ?, downloaded_path = ?, last_error = ? WHERE guid = ?",
                    (status, downloaded_path, last_error, guid),
                )
            elif downloaded_path is not None:
                if clear_last_error:
                    conn.execute(
                        "UPDATE episodes SET status = ?, downloaded_path = ?, last_error = NULL WHERE guid = ?",
                        (status, downloaded_path, guid),
                    )
                else:
                    conn.execute(
                        "UPDATE episodes SET status = ?, downloaded_path = ? WHERE guid = ?",
                        (status, downloaded_path, guid),
                    )
            elif last_error is not None:
                conn.execute(
                    "UPDATE episodes SET status = ?, last_error = ? WHERE guid = ?",
                    (status, last_error, guid),
                )
            elif clear_last_error:
                conn.execute(
                    "UPDATE episodes SET status = ?, last_error = NULL WHERE guid = ?",
                    (status, guid),
                )
            else:
                conn.execute("UPDATE episodes SET status = ? WHERE guid = ?", (status, guid))
            conn.commit()

    def remove_feed(self, feed_url: str) -> PodcastFeed | None:
        # Elimina una suscripción de podcast y sus datos.
        removed = self.get_feed(feed_url)
        if removed is None:
            return None
        with self._connection() as conn:
            conn.execute("DELETE FROM feeds WHERE feed_url = ?", (feed_url,))
            conn.commit()
        return removed
