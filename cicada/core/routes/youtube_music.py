"""Endpoints de resolución y descarga para YouTube Music."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from cicada.core.processing import process_youtube_music_selected_tracks
from cicada.core.state import process_control, youtube_music_provider

router = APIRouter()


class YouTubeMusicResolveRequest(BaseModel):
    url: str


class YouTubeMusicTracksDownloadRequest(BaseModel):
    tracks: List[Dict[str, Any]]
    output_dir: str


@router.post("/api/youtube_music/resolve")
async def resolve_youtube_music_url(request: YouTubeMusicResolveRequest):
    # Resuelve pistas desde una URL de YouTube Music.
    try:
        resource_type, resource_id = youtube_music_provider.parse_url(request.url)
        tracks = await youtube_music_provider.get_tracks(resource_type, resource_id)
        return {"tracks": tracks}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inesperado resolviendo el enlace: {e}")


@router.post("/api/youtube_music/download")
async def start_youtube_music_tracks_download(request: YouTubeMusicTracksDownloadRequest, background_tasks: BackgroundTasks):
    # Inicia la descarga en segundo plano de YouTube Music.
    if not request.tracks:
        raise HTTPException(status_code=400, detail="No se seleccionó ninguna pista para descargar.")
    process_control.cancel_requested = False
    background_tasks.add_task(process_youtube_music_selected_tracks, request.tracks, request.output_dir)
    return {"message": "Descarga de pistas seleccionadas iniciada en segundo plano"}

