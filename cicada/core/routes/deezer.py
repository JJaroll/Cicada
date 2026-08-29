"""Router de Deezer: resolución de track/álbum/playlist públicos por link/ID
(sin login) e inicio de descarga de pistas ya resueltas. Mismo patrón que
routes/spotify.py y routes/youtube_music.py — ver docs/MUSIC_PROVIDERS.md
para el diseño de MusicProvider que los tres implementan.

"Mis playlists" (requiere auth de usuario) queda fuera de este router: se
consulta deezer_provider.requires_auth_for_own_library antes de ofrecer esa
opción en la UI, no se expone un endpoint que solo pueda fallar."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from cicada.core.processing import process_deezer_selected_tracks
from cicada.core.state import deezer_provider, process_control

router = APIRouter()


class DeezerResolveRequest(BaseModel):
    url: str


class DeezerTracksDownloadRequest(BaseModel):
    tracks: List[Dict[str, Any]]
    output_dir: str


@router.post("/api/deezer/resolve")
async def resolve_deezer_url(request: DeezerResolveRequest):
    try:
        resource_type, resource_id = deezer_provider.parse_url(request.url)
        tracks = await deezer_provider.get_tracks(resource_type, resource_id)
        return {"tracks": tracks}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inesperado resolviendo el enlace: {e}")


@router.post("/api/deezer/download")
async def start_deezer_tracks_download(request: DeezerTracksDownloadRequest, background_tasks: BackgroundTasks):
    if not request.tracks:
        raise HTTPException(status_code=400, detail="No se seleccionó ninguna pista para descargar.")
    process_control.cancel_requested = False
    background_tasks.add_task(process_deezer_selected_tracks, request.tracks, request.output_dir)
    return {"message": "Descarga de pistas seleccionadas iniciada en segundo plano"}
