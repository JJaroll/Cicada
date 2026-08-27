"""Confirma que el campo `guid` que el carrito de sync agrega a los
ítems de podcast (solo para uso local en frontend, ver
library_podcasts.js:commitPodcastSelectionToIpod) no rompe la
validación de MediaTrackInput cuando un ítem de música o audiolibro
—que nunca tiene ese campo— pasa por el mismo pipeline de sync.

MediaTrackInput (cicada/ipod/api.py) no declara model_config con
extra="forbid", así que Pydantic v2 ignora silenciosamente cualquier
campo no declarado — este test lo confirma explícitamente en vez de
asumirlo por inspección de código.
"""
from __future__ import annotations

from cicada.ipod.api import MediaTrackInput


def test_campo_extra_guid_es_ignorado_sin_error():
    ti = MediaTrackInput(
        source_path="/tmp/episode.mp3",
        title="Episodio de prueba",
        kind="podcast",
        guid="0d98c727-f940-44a9-b4f4-9580987dcc0e",
    )
    assert ti.source_path == "/tmp/episode.mp3"
    assert not hasattr(ti, "guid")


def test_item_de_musica_sin_guid_no_se_ve_afectado():
    ti = MediaTrackInput(source_path="/tmp/song.mp3", title="Canción", kind="music")
    assert ti.kind == "music"
    assert not hasattr(ti, "guid")


def test_item_de_audiolibro_sin_guid_no_se_ve_afectado():
    ti = MediaTrackInput(source_path="/tmp/book.m4b", title="Audiolibro", kind="audiobook")
    assert ti.kind == "audiobook"
    assert not hasattr(ti, "guid")


def test_carrito_mixto_con_y_sin_guid_valida_uniformemente():
    """Simula el payload real que arma syncBasketToIpod() cuando el carrito
    mezcla música (sin guid), audiolibro (sin guid) y podcast (el frontend
    nunca envía guid al backend — se filtra localmente antes de armar
    `tracks` — pero este test cubre el caso extremo de que llegara igual)."""
    raw_items = [
        {"source_path": "/tmp/song.mp3", "title": "Canción", "kind": "music"},
        {"source_path": "/tmp/book.m4b", "title": "Audiolibro", "kind": "audiobook"},
        {"source_path": "/tmp/ep.mp3", "title": "Episodio", "kind": "podcast", "guid": "abc-123"},
    ]
    parsed = [MediaTrackInput(**item) for item in raw_items]
    assert [t.kind for t in parsed] == ["music", "audiobook", "podcast"]
    assert all(not hasattr(t, "guid") for t in parsed)
