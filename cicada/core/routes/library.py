"""Router de biblioteca local: emparejado con Spotify, info/edición de tracks,
generación de playlists, navegación, artwork y streaming de audio."""
from __future__ import annotations

import asyncio
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

from cicada.core.state import (
    audio_processor,
    load_app_config,
    playlist_manager,
    save_app_config,
)
from cicada.shared.artwork import extract_embedded_artwork

router = APIRouter()

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


class LibraryMatchRequest(BaseModel):
    tracks: List[Dict[str, Any]]
    library_dir: str


class ManualMatchRequest(BaseModel):
    track: Dict[str, Any]
    file_path: str
    library_dir: str


class GeneratePlaylistRequest(BaseModel):
    playlist_name: str
    file_paths: List[str]
    output_dir: str


class LibraryConfigRequest(BaseModel):
    library_dir: str


class TrackActionRequest(BaseModel):
    path: str


class TrackInfoUpdateRequest(BaseModel):
    path: str
    metadata: Dict[str, Any]


def _match_tracks_against_library(tracks: List[Dict[str, Any]], library_dir: str) -> List[Dict[str, Any]]:
    local_index = playlist_manager.index_local_library(library_dir)
    matches = []
    for track in tracks:
        path = playlist_manager.match_track(track, local_index)
        match = dict(track)
        match["path"] = path
        matches.append(match)
    return matches


@router.post("/api/library/match")
async def match_library_tracks(request: LibraryMatchRequest):
    try:
        matches = await asyncio.to_thread(_match_tracks_against_library, request.tracks, request.library_dir)
        return {"matches": matches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error buscando coincidencias en tu biblioteca: {e}")


@router.post("/api/library/manual_match")
async def manual_match_track(request: ManualMatchRequest):
    """
    Asociación manual: el usuario eligió a mano qué archivo local corresponde
    a un track de Spotify que el fuzzy matching no pudo encontrar solo (por
    ejemplo, porque Shazam/AcoustID nunca lo identificaron correctamente y
    quedó con tags genéricos). Re-etiqueta ese archivo con los metadatos
    reales del track de Spotify y lo reorganiza dentro de la biblioteca,
    igual que el resto del pipeline de Cicada.
    """
    try:
        new_path = await audio_processor.apply_metadata_and_move(request.file_path, request.library_dir, request.track)
        return {"path": new_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error re-etiquetando el archivo: {e}")


@router.post("/api/library/show_in_folder")
async def show_in_folder(request: TrackActionRequest):
    import platform
    import subprocess
    import os
    path = request.path
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="El archivo no existe.")
    try:
        sys_plat = platform.system()
        if sys_plat == 'Darwin':
            subprocess.run(['open', '-R', path])
        elif sys_plat == 'Windows':
            subprocess.run(['explorer', '/select,', path])
        else:
            subprocess.run(['dbus-send', '--session', '--dest=org.freedesktop.FileManager1', '--type=method_call', '--print-reply', '/org/freedesktop/FileManager1', 'org.freedesktop.FileManager1.ShowItems', f'array:string:"file://{path}"', 'string:""'])
        return {"message": "Carpeta abierta"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error abriendo la carpeta: {e}")


@router.delete("/api/library/track")
async def delete_track(request: TrackActionRequest):
    import os
    path = request.path
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="El archivo no existe.")
    try:
        os.remove(path)
        return {"message": "Archivo eliminado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando el archivo: {e}")


@router.get("/api/library/track_info")
async def get_track_info(path: str):
    import os
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="El archivo no existe.")
    try:
        meta = await asyncio.to_thread(audio_processor.read_full_metadata, path)
        return meta
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo metadatos: {e}")


@router.post("/api/library/track_info")
async def update_track_info(request: TrackInfoUpdateRequest):
    import os
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="El archivo original no existe.")

    config = load_app_config()
    library_dir = config.get("library_dir")
    if not library_dir:
        raise HTTPException(status_code=400, detail="El directorio de la biblioteca no está configurado.")

    try:
        new_path = await audio_processor.apply_metadata_and_move(request.path, library_dir, request.metadata)
        return {"path": new_path, "message": "Metadatos actualizados"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando metadatos: {e}")


@router.post("/api/library/generate_playlist")
async def generate_playlist_file(request: GeneratePlaylistRequest):
    if not request.file_paths:
        raise HTTPException(status_code=400, detail="No se especificaron canciones para la playlist.")
    try:
        m3u8_path = await asyncio.to_thread(
            playlist_manager.generate_m3u8, request.playlist_name, request.file_paths, request.output_dir
        )
        return {"m3u8_path": m3u8_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando la playlist: {e}")


@router.get("/api/library/config")
async def get_library_config():
    config = load_app_config()
    return {"library_dir": config.get("library_dir", "")}


@router.post("/api/library/config")
async def set_library_config(request: LibraryConfigRequest):
    config = load_app_config()
    config["library_dir"] = request.library_dir
    save_app_config(config)
    return {"library_dir": request.library_dir}


@router.get("/api/library/browse")
async def browse_library(library_dir: str):
    if not library_dir:
        raise HTTPException(status_code=400, detail="Falta especificar la carpeta de biblioteca.")
    try:
        tracks = await asyncio.to_thread(playlist_manager.index_local_library, library_dir)
        playlists = await asyncio.to_thread(playlist_manager.scan_local_playlists, library_dir)
        return {"tracks": tracks, "playlists": playlists}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error escaneando la biblioteca: {e}")


def _resolve_path_within_library(raw_path: str) -> Path:
    library_dir = load_app_config().get("library_dir", "")
    if not library_dir:
        raise HTTPException(status_code=400, detail="No hay una biblioteca configurada.")

    base = Path(library_dir).resolve()
    target = Path(raw_path).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=403, detail="Ruta fuera de la biblioteca configurada.")

    if not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    return target


@router.get("/api/library/artwork")
async def get_track_artwork(path: str):
    target = _resolve_path_within_library(path)
    image_bytes, mime = await asyncio.to_thread(extract_embedded_artwork, target)
    if not image_bytes:
        raise HTTPException(status_code=404, detail="Este archivo no tiene carátula embebida.")
    return Response(content=image_bytes, media_type=mime or "image/jpeg")


def _iter_file_range(file_path: Path, start: int, length: int, chunk_size: int = 65536):
    with open(file_path, "rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            data = f.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


@router.get("/api/library/stream")
async def stream_track(path: str, request: Request):

    target = _resolve_path_within_library(path)
    file_size = target.stat().st_size
    media_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"

    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(str(target), media_type=media_type, headers={"Accept-Ranges": "bytes"})

    match = _RANGE_RE.match(range_header)
    if not match:
        raise HTTPException(status_code=416, detail="Cabecera Range no válida.")

    start_str, end_str = match.groups()
    if start_str == "" and end_str != "":
        suffix_length = int(end_str)
        start = max(file_size - suffix_length, 0)
        end = file_size - 1
    else:
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
        end = min(end, file_size - 1)

    if start > end or start >= file_size:
        raise HTTPException(status_code=416, detail="Rango fuera de los límites del archivo.")

    content_length = end - start + 1
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
    }
    return StreamingResponse(
        _iter_file_range(target, start, content_length),
        status_code=206,
        media_type=media_type,
        headers=headers,
    )
