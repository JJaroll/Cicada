"""Tests para cicada/podcasts/subscription_store.py."""
from __future__ import annotations

from pathlib import Path

from cicada.podcasts.models import PodcastEpisode, PodcastFeed
from cicada.podcasts.subscription_store import SubscriptionStore


def _sample_feed(feed_url: str = "https://example.com/feed.xml") -> PodcastFeed:
    return PodcastFeed(
        feed_url=feed_url,
        title="Show de Prueba",
        author="Autor Test",
        description="Descripción",
        artwork_url="https://example.com/art.jpg",
        category="Technology",
        language="es",
        last_refreshed=1000.0,
        episodes=[
            PodcastEpisode(
                guid="ep-1",
                title="Episodio 1",
                description="Primer episodio",
                audio_url="https://example.com/ep1.mp3",
                pub_date=900.0,
                duration_seconds=1800,
                size_bytes=12345,
                episode_number=1,
                season_number=1,
            ),
            PodcastEpisode(
                guid="ep-2",
                title="Episodio 2",
                audio_url="https://example.com/ep2.mp3",
                pub_date=950.0,
                duration_seconds=2000,
            ),
        ],
    )


def test_add_feed_y_get_feed_roundtrip(tmp_path: Path):
    store = SubscriptionStore(db_path=tmp_path / "podcasts.db")
    feed = _sample_feed()
    store.add_feed(feed)

    fetched = store.get_feed(feed.feed_url)
    assert fetched is not None
    assert fetched.title == "Show de Prueba"
    assert fetched.author == "Autor Test"
    assert len(fetched.episodes) == 2
    # Orden: pub_date DESC
    assert fetched.episodes[0].guid == "ep-2"
    assert fetched.episodes[1].guid == "ep-1"


def test_get_feed_inexistente_devuelve_none(tmp_path: Path):
    store = SubscriptionStore(db_path=tmp_path / "podcasts.db")
    assert store.get_feed("https://no-existe.com/feed.xml") is None


def test_get_feeds_lista_todas_las_suscripciones(tmp_path: Path):
    store = SubscriptionStore(db_path=tmp_path / "podcasts.db")
    store.add_feed(_sample_feed("https://a.com/feed.xml"))
    store.add_feed(_sample_feed("https://b.com/feed.xml"))

    feeds = store.get_feeds()
    assert len(feeds) == 2
    assert {f.feed_url for f in feeds} == {"https://a.com/feed.xml", "https://b.com/feed.xml"}


def test_add_feed_es_idempotente_actualiza_no_duplica(tmp_path: Path):
    store = SubscriptionStore(db_path=tmp_path / "podcasts.db")
    feed = _sample_feed()
    store.add_feed(feed)

    feed.title = "Show Renombrado"
    feed.episodes.append(
        PodcastEpisode(guid="ep-3", title="Episodio 3", audio_url="https://example.com/ep3.mp3", pub_date=1050.0)
    )
    store.add_feed(feed)

    feeds = store.get_feeds()
    assert len(feeds) == 1
    assert feeds[0].title == "Show Renombrado"
    assert len(feeds[0].episodes) == 3


def test_add_feed_preserva_status_local_al_actualizar_episodio_existente(tmp_path: Path):
    store = SubscriptionStore(db_path=tmp_path / "podcasts.db")
    feed = _sample_feed()
    store.add_feed(feed)

    # Simula estado local de descarga (lo haría la Etapa B)
    fetched = store.get_feed(feed.feed_url)
    fetched.episodes[0].status = "downloaded"
    fetched.episodes[0].downloaded_path = "/tmp/ep2.mp3"
    store.update_feed(fetched)

    fetched_again = store.get_feed(feed.feed_url)
    ep2 = next(e for e in fetched_again.episodes if e.guid == "ep-2")
    assert ep2.status == "downloaded"
    assert ep2.downloaded_path == "/tmp/ep2.mp3"


def test_remove_feed_borra_feed_y_episodios_en_cascada(tmp_path: Path):
    db_path = tmp_path / "podcasts.db"
    store = SubscriptionStore(db_path=db_path)
    feed = _sample_feed()
    store.add_feed(feed)

    removed = store.remove_feed(feed.feed_url)
    assert removed is not None
    assert removed.title == "Show de Prueba"
    assert store.get_feed(feed.feed_url) is None

    # Los episodios también deben haberse ido (cascada) — verificado a bajo nivel.
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM episodes WHERE feed_url = ?", (feed.feed_url,)).fetchone()[0]
    conn.close()
    assert count == 0


def test_remove_feed_inexistente_devuelve_none(tmp_path: Path):
    store = SubscriptionStore(db_path=tmp_path / "podcasts.db")
    assert store.remove_feed("https://no-existe.com/feed.xml") is None


def test_db_persiste_entre_instancias_del_store(tmp_path: Path):
    db_path = tmp_path / "podcasts.db"
    SubscriptionStore(db_path=db_path).add_feed(_sample_feed())

    reopened = SubscriptionStore(db_path=db_path)
    feeds = reopened.get_feeds()
    assert len(feeds) == 1
    assert feeds[0].episodes[0].guid in ("ep-1", "ep-2")
