"""Tests para la lógica de playlists y Saved Tracks en DownloadManager."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest
import httpx

from cicada.core.download_manager import DownloadManager


def test_parse_spotify_url_standard_resources():
    dm = DownloadManager()
    assert dm._parse_spotify_url("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT") == ("track", "4cOdK2wGLETKBW3PvgPWqT")
    assert dm._parse_spotify_url("https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3") == ("album", "1DFixLWuPkv3KT3TnV35m3")
    assert dm._parse_spotify_url("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M") == ("playlist", "37i9dQZF1DXcBWIGoYBM5M")
    assert dm._parse_spotify_url("https://open.spotify.com/intl-es/playlist/37i9dQZF1DXcBWIGoYBM5M") == ("playlist", "37i9dQZF1DXcBWIGoYBM5M")


def test_parse_spotify_url_liked_songs():
    dm = DownloadManager()
    assert dm._parse_spotify_url("https://open.spotify.com/collection/tracks") == ("collection", "tracks")
    assert dm._parse_spotify_url("https://open.spotify.com/intl-es/collection/tracks") == ("collection", "tracks")
    assert dm._parse_spotify_url("liked-songs") == ("collection", "tracks")
    assert dm._parse_spotify_url("spotify:collection:tracks") == ("collection", "tracks")
    assert dm._parse_spotify_url("collection/tracks") == ("collection", "tracks")


@pytest.mark.asyncio
async def test_get_user_playlists_filters_non_owned_and_adds_liked_songs():
    dm = DownloadManager()

    mock_user_profile = {"id": "user_me", "display_name": "My Name"}
    mock_liked_response = {"total": 42, "items": []}
    mock_playlists_response = {
        "items": [
            {"id": "p1", "name": "Mi Playlist Propia", "owner": {"id": "user_me"}, "collaborative": False, "tracks": {"total": 10}, "images": []},
            {"id": "p2", "name": "Playlist de un Amigo", "owner": {"id": "other_user"}, "collaborative": False, "tracks": {"total": 20}, "images": []},
            {"id": "p3", "name": "Playlist Colaborativa", "owner": {"id": "other_user"}, "collaborative": True, "tracks": {"total": 15}, "images": []},
            {"id": "p4", "name": "Today's Top Hits (Spotify)", "owner": {"id": "spotify"}, "collaborative": False, "tracks": {"total": 50}, "images": []},
        ],
        "next": None
    }

    async def mock_get(url, headers=None, params=None):
        req = httpx.Request("GET", url)
        if "api.spotify.com/v1/me/tracks" in url:
            return httpx.Response(200, json=mock_liked_response, request=req)
        elif url == "https://api.spotify.com/v1/me":
            return httpx.Response(200, json=mock_user_profile, request=req)
        elif "api.spotify.com/v1/me/playlists" in url:
            return httpx.Response(200, json=mock_playlists_response, request=req)
        return httpx.Response(404, request=req)

    with patch.object(dm, "get_user_token", AsyncMock(return_value="mock_token")):
        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            playlists = await dm.get_user_playlists()

    # Debe incluir 'liked-songs', 'p1' (propia) y 'p3' (colaborativa)
    # Debe haber descartado 'p2' (ajena) y 'p4' (spotify)
    assert len(playlists) == 3

    assert playlists[0]["id"] == "liked-songs"
    assert playlists[0]["is_liked"] is True
    assert playlists[0]["track_count"] == 42

    assert playlists[1]["id"] == "p1"
    assert playlists[1]["name"] == "Mi Playlist Propia"

    assert playlists[2]["id"] == "p3"
    assert playlists[2]["name"] == "Playlist Colaborativa"


@pytest.mark.asyncio
async def test_get_spotify_tracks_resolves_liked_songs():
    dm = DownloadManager()

    mock_saved_tracks_response = {
        "items": [
            {
                "track": {
                    "id": "t1",
                    "name": "Favorite Song 1",
                    "artists": [{"name": "Great Artist"}],
                    "album": {"name": "Great Album", "release_date": "2023-01-01", "images": []},
                    "track_number": 1,
                    "external_ids": {"isrc": "US1234567890"}
                }
            }
        ],
        "next": None
    }

    async def mock_get(url, headers=None, params=None):
        req = httpx.Request("GET", url)
        if "api.spotify.com/v1/me/tracks" in url:
            return httpx.Response(200, json=mock_saved_tracks_response, request=req)
        elif "audio-features" in url:
            return httpx.Response(200, json={"audio_features": [{"id": "t1", "tempo": 128.0}]}, request=req)
        return httpx.Response(404, request=req)

    with patch.object(dm, "get_user_token", AsyncMock(return_value="mock_token")):
        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            tracks = await dm.get_spotify_tracks("https://open.spotify.com/collection/tracks")

    assert len(tracks) == 1
    assert tracks[0]["title"] == "Favorite Song 1"
    assert tracks[0]["artist"] == "Great Artist"
    assert tracks[0]["bpm"] == 128
    assert tracks[0]["external_ids"] == {"isrc": "US1234567890"}
