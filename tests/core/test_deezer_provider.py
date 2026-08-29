"""Tests para DeezerProvider: parseo de URL/ID, mapeo de metadata, y el fix
de la asimetría de /album/{id}/tracks (no repite el objeto "album" completo
por item, a diferencia de /playlist/{id}/tracks). Sin red — httpx se mockea,
igual que en test_spotify_playlists.py."""
from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from cicada.core.providers.deezer import DeezerProvider


def _make_provider() -> DeezerProvider:
    return DeezerProvider()


def test_flags_declared_correctly():
    p = _make_provider()
    assert p.name == "deezer"
    assert p.supports_public_playlist_by_id is True
    assert p.requires_auth_for_own_library is True
    assert p.supported_resource_types == ("track", "album", "playlist")
    assert p.is_authenticated() is False


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.deezer.com/playlist/1313621735", ("playlist", "1313621735")),
        ("https://www.deezer.com/us/playlist/1313621735", ("playlist", "1313621735")),
        ("https://www.deezer.com/us/playlist/1313621735?utm_source=x", ("playlist", "1313621735")),
        ("https://www.deezer.com/en/track/4058916481", ("track", "4058916481")),
        ("https://www.deezer.com/album/996462431", ("album", "996462431")),
        ("1313621735", ("playlist", "1313621735")),  # id suelto: se asume playlist
    ],
)
def test_parse_url(url, expected):
    p = _make_provider()
    assert p.parse_url(url) == expected


def test_parse_url_rejects_unrecognized_input():
    p = _make_provider()
    with pytest.raises(ValueError):
        p.parse_url("https://music.youtube.com/playlist?list=PLxxxx")


def test_parse_short_url():
    p = _make_provider()
    mock_resp = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", "https://www.deezer.com/mx/track/5664764"),
    )
    with patch("httpx.Client.get", return_value=mock_resp):
        assert p.parse_url("https://link.deezer.com/s/34fMkSoReh8LfLWLuvWSz") == ("track", "5664764")


@pytest.mark.asyncio
async def test_get_tracks_rejects_unsupported_resource_type():
    p = _make_provider()
    with pytest.raises(ValueError):
        await p.get_tracks("collection", "some_id")


@pytest.mark.asyncio
async def test_get_tracks_for_track_resource():
    p = _make_provider()
    mock_track = {
        "id": 4058916481,
        "title": 'I Knew It, I Knew You (From "Toy Story 5")',
        "isrc": "USWD12641055",
        "artist": {"name": "Taylor Swift"},
        "album": {"title": "I Knew It, I Knew You", "cover_xl": "https://img/xl.jpg"},
    }

    async def mock_get(url, **kwargs):
        req = httpx.Request("GET", url)
        assert url == "https://api.deezer.com/track/4058916481"
        return httpx.Response(200, json=mock_track, request=req)

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        tracks = await p.get_tracks("track", "4058916481")

    assert len(tracks) == 1
    assert tracks[0]["title"] == 'I Knew It, I Knew You (From "Toy Story 5")'
    assert tracks[0]["artist"] == "Taylor Swift"
    assert tracks[0]["provider_track_id"] == "4058916481"
    assert tracks[0]["album"] == "I Knew It, I Knew You"
    assert tracks[0]["artwork_url"] == "https://img/xl.jpg"
    assert tracks[0]["external_ids"] == {"isrc": "USWD12641055"}
    assert "bpm" not in tracks[0]  # deliberadamente omitido — ver docstring del módulo


@pytest.mark.asyncio
async def test_get_tracks_for_playlist_paginates():
    p = _make_provider()
    page1 = {
        "data": [
            {"id": 1, "title": "Track 1", "artist": {"name": "A1"}, "album": {"title": "Alb1"}},
        ],
        "next": "https://api.deezer.com/playlist/999/tracks?index=1",
    }
    page2 = {
        "data": [
            {"id": 2, "title": "Track 2", "artist": {"name": "A2"}, "album": {"title": "Alb2"}},
        ],
        "next": None,
    }

    async def mock_get(url, **kwargs):
        req = httpx.Request("GET", url)
        if url == "https://api.deezer.com/playlist/999/tracks":
            return httpx.Response(200, json=page1, request=req)
        if "index=1" in url:
            return httpx.Response(200, json=page2, request=req)
        return httpx.Response(404, request=req)

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        tracks = await p.get_tracks("playlist", "999")

    assert len(tracks) == 2
    assert tracks[0]["title"] == "Track 1"
    assert tracks[1]["title"] == "Track 2"


@pytest.mark.asyncio
async def test_get_tracks_for_album_backfills_missing_album_metadata():
    # Regresión del hallazgo real: /album/{id}/tracks no repite el objeto
    # "album" completo por item (a diferencia de playlist) — get_tracks()
    # debe completar título/carátula desde GET /album/{id} por separado.
    p = _make_provider()
    album_response = {"id": 996462431, "title": "Discovery", "cover_xl": "https://img/discovery.jpg"}
    tracks_response = {
        "data": [
            {"id": 10, "title": "One More Time", "artist": {"name": "Daft Punk"}},
            {"id": 11, "title": "Aerodynamic", "artist": {"name": "Daft Punk"}},
        ],
        "next": None,
    }

    async def mock_get(url, **kwargs):
        req = httpx.Request("GET", url)
        if url == "https://api.deezer.com/album/996462431":
            return httpx.Response(200, json=album_response, request=req)
        if url == "https://api.deezer.com/album/996462431/tracks":
            return httpx.Response(200, json=tracks_response, request=req)
        return httpx.Response(404, request=req)

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        tracks = await p.get_tracks("album", "996462431")

    assert len(tracks) == 2
    for t in tracks:
        assert t["album"] == "Discovery"
        assert t["artwork_url"] == "https://img/discovery.jpg"


@pytest.mark.asyncio
async def test_get_tracks_raises_on_deezer_error_payload():
    # Deezer responde 200 con {"error": {...}} para IDs inexistentes, no 404.
    p = _make_provider()
    error_response = {"error": {"type": "DataException", "message": "no data", "code": 800}}

    async def mock_get(url, **kwargs):
        req = httpx.Request("GET", url)
        return httpx.Response(200, json=error_response, request=req)

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        with pytest.raises(ValueError):
            await p.get_tracks("playlist", "0")


@pytest.mark.asyncio
async def test_get_user_playlists_raises_not_implemented():
    p = _make_provider()
    with pytest.raises(NotImplementedError):
        await p.get_user_playlists()
