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
    assert p.supported_resource_types == ("playlist",)
    assert p.is_authenticated() is False


def test_parse_url_from_full_playlist_url():
    p = _make_provider()
    url = "https://music.youtube.com/playlist?list=PLg48S-qywklvkpUTFRQ3MLaAbHdl_BXMY"
    assert p.parse_url(url) == ("playlist", "PLg48S-qywklvkpUTFRQ3MLaAbHdl_BXMY")


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
    assert "album" not in tracks[0]  # sin álbum, no se agrega la clave

    assert tracks[1]["album"] == "Álbum Real"
    assert tracks[1]["provider_track_id"] == "abc123"


@pytest.mark.asyncio
async def test_get_tracks_rejects_non_playlist_resource_type():
    p = _make_provider()
    with pytest.raises(ValueError):
        await p.get_tracks("album", "some_id")


@pytest.mark.asyncio
async def test_get_user_playlists_raises_not_implemented():
    p = _make_provider()
    with pytest.raises(NotImplementedError):
        await p.get_user_playlists()
