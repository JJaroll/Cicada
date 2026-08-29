"""Tests para YouTubeMusicProvider: parseo de URL/ID y mapeo de metadata de
ytmusicapi a TrackMeta. Sin red — ytmusicapi.YTMusic se mockea, igual que
httpx se mockea en test_spotify_playlists.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cicada.core.providers.youtube_music import YouTubeMusicProvider


def _make_provider() -> YouTubeMusicProvider:
    with patch("cicada.core.providers.youtube_music.YTMusic"):
        return YouTubeMusicProvider()


def test_flags_declared_correctly():
    p = _make_provider()
    assert p.name == "youtube_music"
    assert p.supports_public_playlist_by_id is True
    assert p.requires_auth_for_own_library is True
    assert p.supported_resource_types == ("track", "album", "playlist")
    assert p.is_authenticated() is False


def test_parse_url_from_full_playlist_url():
    p = _make_provider()
    url = "https://music.youtube.com/playlist?list=PLg48S-qywklvkpUTFRQ3MLaAbHdl_BXMY"
    assert p.parse_url(url) == ("playlist", "PLg48S-qywklvkpUTFRQ3MLaAbHdl_BXMY")


def test_parse_url_from_track_urls():
    p = _make_provider()
    assert p.parse_url("https://music.youtube.com/watch?v=M15XORZCg_I&si=ECdCmtUWpx9DrkYr") == ("track", "M15XORZCg_I")
    assert p.parse_url("https://www.youtube.com/watch?v=M15XORZCg_I") == ("track", "M15XORZCg_I")
    assert p.parse_url("https://youtu.be/M15XORZCg_I") == ("track", "M15XORZCg_I")


def test_parse_url_from_album_urls():
    p = _make_provider()
    assert p.parse_url("https://music.youtube.com/browse/MPREb_0VIWd3F7iSL") == ("album", "MPREb_0VIWd3F7iSL")
    assert p.parse_url("MPREb_0VIWd3F7iSL") == ("album", "MPREb_0VIWd3F7iSL")


def test_parse_url_with_extra_query_params():
    p = _make_provider()
    url = "https://music.youtube.com/playlist?list=PLabc123&feature=share"
    assert p.parse_url(url) == ("playlist", "PLabc123")


def test_parse_url_from_bare_id():
    p = _make_provider()
    assert p.parse_url("PLg48S-qywklvkpUTFRQ3MLaAbHdl_BXMY") == (
        "playlist",
        "PLg48S-qywklvkpUTFRQ3MLaAbHdl_BXMY",
    )


def test_parse_url_strips_vl_browse_prefix():
    # yt.search() devuelve browseId con prefijo "VL"; get_playlist() lo
    # rechaza — hay que despojarlo tanto si viene de una URL como de un ID suelto.
    p = _make_provider()
    assert p.parse_url("VLPLg48S-qywklvkpUTFRQ3MLaAbHdl_BXMY") == (
        "playlist",
        "PLg48S-qywklvkpUTFRQ3MLaAbHdl_BXMY",
    )


def test_parse_url_rejects_unrecognized_input():
    p = _make_provider()
    with pytest.raises(ValueError):
        p.parse_url("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")


@pytest.mark.asyncio
async def test_get_tracks_single_track():
    p = _make_provider()
    p._yt.get_watch_playlist = MagicMock(return_value={
        "tracks": [{
            "title": "Sweet Transvestite",
            "artists": [{"name": "Tim Curry"}],
            "album": {"name": "Rocky Horror Soundtrack"},
            "thumbnail": [{"url": "https://img/544.jpg", "width": 544}],
        }]
    })

    tracks = await p.get_tracks("track", "M15XORZCg_I")
    assert len(tracks) == 1
    assert tracks[0]["title"] == "Sweet Transvestite"
    assert tracks[0]["artist"] == "Tim Curry"
    assert tracks[0]["album"] == "Rocky Horror Soundtrack"
    assert tracks[0]["provider_track_id"] == "M15XORZCg_I"
    assert tracks[0]["artwork_url"] == "https://img/544.jpg"


@pytest.mark.asyncio
async def test_get_tracks_album():
    p = _make_provider()
    p._yt.get_album = MagicMock(return_value={
        "title": "Rocky Horror Soundtrack",
        "thumbnails": [{"url": "https://img/album.jpg", "width": 500}],
        "artists": [{"name": "Various Artists"}],
        "tracks": [
            {
                "title": "Track 1",
                "artists": [{"name": "Artist 1"}],
                "videoId": "vid1",
                "thumbnails": [],
            },
            {
                "title": "Track 2",
                "artists": [],
                "videoId": "vid2",
                "thumbnails": [],
            }
        ]
    })

    tracks = await p.get_tracks("album", "MPREb_0VIWd3F7iSL")
    assert len(tracks) == 2
    assert tracks[0]["title"] == "Track 1"
    assert tracks[0]["artist"] == "Artist 1"
    assert tracks[0]["artwork_url"] == "https://img/album.jpg"
    assert tracks[1]["artist"] == "Various Artists"


@pytest.mark.asyncio
async def test_get_tracks_maps_metadata_correctly():
    p = _make_provider()
    mock_playlist_response = {
        "title": "Mi playlist",
        "tracks": [
            {
                "title": "Choosin' Texas",
                "artists": [{"name": "Ella Langley"}],
                "album": None,
                "videoId": "nUsrYVxrDwI",
                "thumbnails": [
                    {"url": "https://img/small.jpg", "width": 200},
                    {"url": "https://img/large.jpg", "width": 800},
                ],
            },
            {
                "title": "Con álbum",
                "artists": [{"name": "Artista X"}],
                "album": {"name": "Álbum Real"},
                "videoId": "abc123",
                "thumbnails": [],
            },
            {
                # Sin videoId: debe descartarse, no puede descargarse ni identificarse.
                "title": "Sin video id",
                "artists": [{"name": "Nadie"}],
                "videoId": None,
                "thumbnails": [],
            },
        ],
    }
    p._yt.get_playlist = MagicMock(return_value=mock_playlist_response)

    tracks = await p.get_tracks("playlist", "PLxxxx")

    assert len(tracks) == 2  # el track sin videoId se descarta

    assert tracks[0]["title"] == "Choosin' Texas"
    assert tracks[0]["artist"] == "Ella Langley"
    assert tracks[0]["provider_track_id"] == "nUsrYVxrDwI"
    assert tracks[0]["artwork_url"] == "https://img/large.jpg"  # el thumbnail más grande
    assert tracks[0].get("album") == "" or "album" not in tracks[0]

    assert tracks[1]["album"] == "Álbum Real"
    assert tracks[1]["provider_track_id"] == "abc123"


@pytest.mark.asyncio
async def test_get_tracks_rejects_non_supported_resource_type():
    p = _make_provider()
    with pytest.raises(ValueError):
        await p.get_tracks("invalid_type", "some_id")


@pytest.mark.asyncio
async def test_get_user_playlists_raises_not_implemented():
    p = _make_provider()
    with pytest.raises(NotImplementedError):
        await p.get_user_playlists()
