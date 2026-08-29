"""Endpoints de autenticación, resolución y descarga de Spotify."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from cicada.core.processing import (
    process_spotify_download,
    process_spotify_selected_tracks,
)
from cicada.core.state import audio_processor, download_manager, process_control

router = APIRouter()


class SpotifyRequest(BaseModel):
    url: str
    output_dir: str


class SpotifyResolveRequest(BaseModel):
    url: str


class SpotifyTracksDownloadRequest(BaseModel):
    tracks: List[Dict[str, Any]]
    output_dir: str


class DownloadSingleTrackRequest(BaseModel):
    track: Dict[str, Any]
    output_dir: str


@router.post("/api/spotify")
async def start_spotify_download(request: SpotifyRequest, background_tasks: BackgroundTasks):
    # Inicia la descarga completa de Spotify en segundo plano.
    process_control.cancel_requested = False
    background_tasks.add_task(process_spotify_download, request.url, request.output_dir)
    return {"message": "Descarga de Spotify iniciada en segundo plano"}


@router.post("/api/spotify/resolve")
async def resolve_spotify_url(request: SpotifyResolveRequest):
    # Resuelve pistas desde una URL de Spotify.
    try:
        tracks = await download_manager.get_spotify_tracks(request.url)
        return {"tracks": tracks}
    except ValueError as e:
        status_code = 401 if "api/auth/login" in str(e) else 400
        raise HTTPException(status_code=status_code, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Spotify rechazó la petición: {e}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar con Spotify: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inesperado resolviendo el enlace: {e}")


@router.post("/api/spotify/download")
async def start_spotify_tracks_download(request: SpotifyTracksDownloadRequest, background_tasks: BackgroundTasks):
    # Inicia la descarga de pistas seleccionadas de Spotify.
    if not request.tracks:
        raise HTTPException(status_code=400, detail="No se seleccionó ninguna pista para descargar.")
    process_control.cancel_requested = False
    background_tasks.add_task(process_spotify_selected_tracks, request.tracks, request.output_dir)
    return {"message": "Descarga de pistas seleccionadas iniciada en segundo plano"}


@router.get("/api/spotify/playlists")
async def list_spotify_playlists():
    # Obtiene las listas de reproducción del usuario de Spotify.
    try:
        playlists = await download_manager.get_user_playlists()
        return {"playlists": playlists}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Spotify rechazó la petición: {e}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar con Spotify: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inesperado listando playlists: {e}")


@router.post("/api/spotify/download_single")
async def download_single_track(request: DownloadSingleTrackRequest):
    # Descarga y etiqueta una pista individual de Spotify.
    try:
        search_query = f"ytsearch1:{request.track.get('artist', '')} {request.track.get('title', '')} Topic"
        file_path = await download_manager.download_audio(search_query, request.output_dir)
        new_path = await audio_processor.apply_metadata_and_move(file_path, request.output_dir, request.track)
        return {"path": str(new_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/auth/login")
async def spotify_login():
    # Redirige al flujo de autenticación OAuth de Spotify.
    try:
        auth_url = download_manager.get_auth_url()
        return RedirectResponse(auth_url)
    except ValueError as e:
        error_msg = quote(str(e))
        return RedirectResponse(url=f"/?spotify_auth=error&reason={error_msg}")


@router.get("/api/auth/status")
async def spotify_auth_status():
    # Consulta el estado de autenticación de Spotify.
    return {"connected": download_manager.TOKEN_FILE.exists()}


@router.get("/api/auth/callback")
async def spotify_callback(code: Optional[str] = None, error: Optional[str] = None):
    # Procesa el callback OAuth de Spotify y guarda tokens.
    if error or not code:
        return RedirectResponse(url=f"/?spotify_auth=error&reason={error or 'missing_code'}")

    try:
        await download_manager.process_auth_code(code)
    except Exception as e:
        return RedirectResponse(url=f"/?spotify_auth=error&reason={e}")

    return RedirectResponse(url="/?spotify_auth=success")

