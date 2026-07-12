"""
Cicada
-----------
Herramienta local de organización musical y sincronización automática de metadatos de alta fidelidad.

Desarrollado por: JJaroll
GitHub: https://github.com/JJaroll
Fecha: 10/07/2026
Licencia: GNU GPLv3
"""

__author__ = "JJaroll"
__version__ = "1.0.1"
__maintainer__ = "JJaroll"
__status__ = "Production"

import mimetypes
import sys
import os

if getattr(sys, 'frozen', False):
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

import json
import asyncio
import random
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dotenv import load_dotenv, set_key

from app_paths import get_app_data_dir

APP_DATA_DIR = get_app_data_dir()
ENV_FILE = APP_DATA_DIR / ".env"
load_dotenv(ENV_FILE)

from metadata_manager import MetadataManager
from audio_processor import AudioProcessor
from download_manager import DownloadManager
from playlist_manager import PlaylistManager
import acoustid_fallback

app = FastAPI()
metadata_manager = MetadataManager()
audio_processor = AudioProcessor()
download_manager = DownloadManager()
playlist_manager = PlaylistManager()

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

CONFIG_FILE = APP_DATA_DIR / ".cicada_config.json"

def load_app_config() -> Dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_app_config(data: Dict[str, Any]) -> None:
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

cancel_requested = False

class ProcessRequest(BaseModel):
    input_dir: str
    output_dir: str

class SpotifyRequest(BaseModel):
    url: str
    output_dir: str

class SpotifyResolveRequest(BaseModel):
    url: str

class SpotifyTracksDownloadRequest(BaseModel):
    tracks: List[Dict[str, Any]]
    output_dir: str

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

class SettingsRequest(BaseModel):
    acoustid_api_key: Optional[str] = None
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None
    plan_c_enabled: Optional[bool] = None
    library_dir: Optional[str] = None
    process_input_dir: Optional[str] = None
    process_output_dir: Optional[str] = None
    theme: Optional[str] = None
    color_accent: Optional[str] = None

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

async def process_library(input_dir: str, output_dir: str):
    await manager.broadcast(json.dumps({"type": "info", "message": f"Iniciando escaneo en: {input_dir}"}))

    plan_c_enabled = bool(load_app_config().get("plan_c_enabled", False))

    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if not input_path.exists() or not input_path.is_dir():
        await manager.broadcast(json.dumps({"type": "error", "message": "Directorio de entrada no válido."}))
        return

    output_path.mkdir(parents=True, exist_ok=True)

    allowed_exts = {'.mp3', '.m4a', '.mp4', '.aac', '.flac', '.wav', '.aiff', '.aif', '.alac'}

    resolved_output = output_path.resolve()
    files_to_process = []
    for f in input_path.rglob("*"):
        if f.is_file() and f.suffix.lower() in allowed_exts:
            try:
                resolved_f = f.resolve()
                if str(resolved_f).startswith(str(resolved_output) + os.sep) or str(resolved_f) == str(resolved_output):
                    continue
            except Exception:
                pass
            files_to_process.append(f)

    total_files = len(files_to_process)
    await manager.broadcast(json.dumps({"type": "info", "message": f"Se encontraron {total_files} archivos."}))

    # --- MEMORIA DE ESTADO ---
    state_file = output_path / ".cicada_state.json"
    processed_files = set()
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)
                processed_files = set(state_data.get("processed", []))
                if processed_files:
                    await manager.broadcast(json.dumps({"type": "info", "message": f"Retomando sesión: {len(processed_files)} archivos ya procesados serán saltados."}))
        except Exception:
            pass

    report = {
        "successes": [],
        "errors": [],
        "incomplete": []
    }

    start_time = time.time()
    session_processed_count = 0

    async def log_callback(msg: str):
        await manager.broadcast(json.dumps({"type": "detail", "message": msg}))

    for idx, file_path in enumerate(files_to_process):
        if cancel_requested:
            await manager.broadcast(json.dumps({"type": "error", "message": "Proceso cancelado por el usuario."}))
            break

        current = idx + 1

        # Saltar archivos ya procesados con éxito en ejecuciones anteriores
        if str(file_path) in processed_files:
            await manager.broadcast(json.dumps({
                "type": "progress",
                "current": current,
                "total": total_files,
                "file": f"(Saltado) {file_path.name}",
                "eta": "Retomando sesión..."
            }))
            continue

        session_processed_count += 1
        elapsed = time.time() - start_time

        eta_str = "Calculando ETA..."
        if session_processed_count > 1:
            avg_time = elapsed / (session_processed_count - 1)
            # Considerar los archivos restantes independientemente de los saltados
            rem_time = avg_time * (total_files - current + 1)
            m, s = divmod(int(rem_time), 60)
            eta_str = f"ETA: {m}m {s}s"
            if m > 60:
                h, m = divmod(m, 60)
                eta_str = f"ETA: {h}h {m}m {s}s"

        await manager.broadcast(json.dumps({
            "type": "progress",
            "current": current,
            "total": total_files,
            "file": file_path.name,
            "eta": eta_str
        }))

        res = await metadata_manager.process_file_metadata(str(file_path), logger_callback=log_callback, plan_c_enabled=plan_c_enabled)

        if not res['success']:
            report['errors'].append({
                "file": str(file_path),
                "error": res.get('error', 'Unknown Error')
            })
            await asyncio.sleep(2)
            continue

        metadata = res['metadata']
        if metadata.get('artwork_url'):
            await manager.broadcast(json.dumps({"type": "cover", "url": metadata.get('artwork_url')}))

        try:
            await log_callback("💾 Escribiendo metadatos ID3 / MP4 y reestructurando...")
            new_path = await audio_processor.apply_metadata_and_move(str(file_path), str(output_path), metadata)

            track_info = {
                "original_file": str(file_path),
                "new_file": str(new_path),
                "title": metadata.get('title'),
                "artist": metadata.get('artist')
            }

            if res['status'] == 'incomplete':
                track_info['missing'] = res['incomplete_fields']
                report['incomplete'].append(track_info)
            else:
                report['successes'].append(track_info)

            processed_files.add(str(file_path))
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"processed": list(processed_files)}, f, ensure_ascii=False)

        except Exception as e:
            report['errors'].append({
                "file": str(file_path),
                "error": f"Error applying tags / moving: {str(e)}"
            })

        # --- RETRASO INTENCIONAL ---
        if current < total_files:
            await log_callback("⏳ Esperando 3 segundos entre canciones (Programación defensiva)...")
            await asyncio.sleep(3)

    report_path = output_path / "cicada_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)

    if cancel_requested:
        await manager.broadcast(json.dumps({"type": "done", "message": "Proceso detenido. (Reporte parcial guardado)", "report_path": str(report_path)}))
    else:
        await manager.broadcast(json.dumps({"type": "done", "message": "Proceso completado.", "report_path": str(report_path)}))

async def _download_and_tag_tracks(tracks: List[Dict[str, Any]], output_dir: str):
    """ Descarga (YouTube Music) e inyecta metadata a una lista ya resuelta de tracks de Spotify. """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    total = len(tracks)
    await manager.broadcast(json.dumps({"type": "info", "message": f"Se van a descargar {total} pista(s)."}))

    for i, track in enumerate(tracks):
        if cancel_requested:
            await manager.broadcast(json.dumps({"type": "error", "message": "Proceso cancelado por el usuario."}))
            break

        await manager.broadcast(json.dumps({
            "type": "progress",
            "current": i + 1,
            "total": total,
            "file": track['title']
        }))
        await manager.broadcast(json.dumps({"type": "cover", "url": track.get('artwork_url', '')}))

        try:
            search_query = f"ytsearch1:{track['artist']} {track['title']} Topic"
            file_path = await download_manager.download_audio(search_query, output_dir)
            await audio_processor.apply_metadata_and_move(file_path, output_dir, track)
        except Exception as e:
            await manager.broadcast(json.dumps({
                "type": "error",
                "message": f"Error descargando '{track['title']}': {e}"
            }))
        finally:
            if i < total - 1:
                await asyncio.sleep(random.uniform(4, 9))

    if cancel_requested:
        await manager.broadcast(json.dumps({"type": "done", "message": "Descarga de Spotify cancelada.", "report_path": ""}))
    else:
        await manager.broadcast(json.dumps({"type": "done", "message": "Descarga de Spotify completada.", "report_path": ""}))

async def process_spotify_download(url: str, output_dir: str):
    await manager.broadcast(json.dumps({"type": "info", "message": f"Resolviendo enlace de Spotify: {url}"}))

    try:
        tracks = await download_manager.get_spotify_tracks(url)
    except Exception as e:
        await manager.broadcast(json.dumps({"type": "error", "message": f"No se pudo leer el enlace de Spotify: {e}"}))
        return

    await manager.broadcast(json.dumps({"type": "info", "message": f"Se encontraron {len(tracks)} pistas en el enlace de Spotify."}))
    await _download_and_tag_tracks(tracks, output_dir)

async def process_spotify_selected_tracks(tracks: List[Dict[str, Any]], output_dir: str):
    await _download_and_tag_tracks(tracks, output_dir)

@app.post("/api/start")
async def start_processing(request: ProcessRequest, background_tasks: BackgroundTasks):
    global cancel_requested
    cancel_requested = False
    background_tasks.add_task(process_library, request.input_dir, request.output_dir)
    return {"message": "Procesamiento iniciado en segundo plano"}

@app.post("/api/spotify")
async def start_spotify_download(request: SpotifyRequest, background_tasks: BackgroundTasks):
    global cancel_requested
    cancel_requested = False
    background_tasks.add_task(process_spotify_download, request.url, request.output_dir)
    return {"message": "Descarga de Spotify iniciada en segundo plano"}

@app.post("/api/spotify/resolve")
async def resolve_spotify_url(request: SpotifyResolveRequest):
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

@app.post("/api/spotify/download")
async def start_spotify_tracks_download(request: SpotifyTracksDownloadRequest, background_tasks: BackgroundTasks):
    global cancel_requested
    if not request.tracks:
        raise HTTPException(status_code=400, detail="No se seleccionó ninguna pista para descargar.")
    cancel_requested = False
    background_tasks.add_task(process_spotify_selected_tracks, request.tracks, request.output_dir)
    return {"message": "Descarga de pistas seleccionadas iniciada en segundo plano"}

@app.get("/api/spotify/playlists")
async def list_spotify_playlists():
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

def _match_tracks_against_library(tracks: List[Dict[str, Any]], library_dir: str) -> List[Dict[str, Any]]:
    local_index = playlist_manager.index_local_library(library_dir)
    matches = []
    for track in tracks:
        path = playlist_manager.match_track(track, local_index)
        match = dict(track)
        match["path"] = path
        matches.append(match)
    return matches

@app.post("/api/library/match")
async def match_library_tracks(request: LibraryMatchRequest):
    try:
        matches = await asyncio.to_thread(_match_tracks_against_library, request.tracks, request.library_dir)
        return {"matches": matches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error buscando coincidencias en tu biblioteca: {e}")

@app.post("/api/library/manual_match")
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

@app.post("/api/library/generate_playlist")
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

@app.get("/api/library/config")
async def get_library_config():
    config = load_app_config()
    return {"library_dir": config.get("library_dir", "")}

@app.post("/api/library/config")
async def set_library_config(request: LibraryConfigRequest):
    config = load_app_config()
    config["library_dir"] = request.library_dir
    save_app_config(config)
    return {"library_dir": request.library_dir}

@app.get("/api/settings")
async def get_settings():
    config = load_app_config()
    return {
        "acoustid_api_key": os.environ.get("ACOUSTID_API_KEY", ""),
        "spotify_client_id": os.environ.get("SPOTIFY_CLIENT_ID", ""),
        "spotify_client_secret": os.environ.get("SPOTIFY_CLIENT_SECRET", ""),
        "plan_c_enabled": bool(config.get("plan_c_enabled", False)),
        "library_dir": config.get("library_dir", ""),
        "process_input_dir": config.get("process_input_dir", ""),
        "process_output_dir": config.get("process_output_dir", ""),
        "theme": config.get("theme", "grafito"),
        "color_accent": config.get("color_accent", "azul"),
    }

@app.post("/api/settings")
async def update_settings(request: SettingsRequest):
    if request.acoustid_api_key is not None:
        os.environ["ACOUSTID_API_KEY"] = request.acoustid_api_key
        acoustid_fallback.ACOUSTID_API_KEY = request.acoustid_api_key
        set_key(str(ENV_FILE), "ACOUSTID_API_KEY", request.acoustid_api_key)

    if request.spotify_client_id is not None:
        os.environ["SPOTIFY_CLIENT_ID"] = request.spotify_client_id
        set_key(str(ENV_FILE), "SPOTIFY_CLIENT_ID", request.spotify_client_id)

    if request.spotify_client_secret is not None:
        os.environ["SPOTIFY_CLIENT_SECRET"] = request.spotify_client_secret
        set_key(str(ENV_FILE), "SPOTIFY_CLIENT_SECRET", request.spotify_client_secret)

    config = load_app_config()
    if request.plan_c_enabled is not None:
        config["plan_c_enabled"] = request.plan_c_enabled
    if request.library_dir is not None:
        config["library_dir"] = request.library_dir
    if request.process_input_dir is not None:
        config["process_input_dir"] = request.process_input_dir
    if request.process_output_dir is not None:
        config["process_output_dir"] = request.process_output_dir
    if request.theme is not None:
        config["theme"] = request.theme
    if request.color_accent is not None:
        config["color_accent"] = request.color_accent
    save_app_config(config)

    return {"message": "Configuración guardada."}

@app.get("/api/library/browse")
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

def _extract_embedded_artwork(file_path: Path):
    try:
        import mutagen
        from mutagen.mp4 import MP4
        from mutagen.flac import FLAC

        audio = mutagen.File(str(file_path))
        if audio is None:
            return None, None

        if isinstance(audio, MP4):
            covers = audio.tags.get("covr") if audio.tags else None
            if covers:
                cover = covers[0]
                mime = "image/png" if cover.imageformat == cover.FORMAT_PNG else "image/jpeg"
                return bytes(cover), mime
            return None, None

        if isinstance(audio, FLAC):
            if audio.pictures:
                pic = audio.pictures[0]
                return pic.data, pic.mime
            return None, None

        # ID3 (mp3, wav, aiff)
        if audio.tags is not None:
            for key in list(audio.tags.keys()):
                if str(key).startswith("APIC"):
                    apic = audio.tags[key]
                    return apic.data, apic.mime

        return None, None
    except Exception:
        return None, None

@app.get("/api/library/artwork")
async def get_track_artwork(path: str):
    target = _resolve_path_within_library(path)
    image_bytes, mime = await asyncio.to_thread(_extract_embedded_artwork, target)
    if not image_bytes:
        raise HTTPException(status_code=404, detail="Este archivo no tiene carátula embebida.")
    return Response(content=image_bytes, media_type=mime or "image/jpeg")

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")

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

@app.get("/api/library/stream")
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

@app.get("/api/auth/login")
async def spotify_login():
    auth_url = download_manager.get_auth_url()
    return RedirectResponse(auth_url)

@app.get("/api/auth/status")
async def spotify_auth_status():
    return {"connected": download_manager.TOKEN_FILE.exists()}

@app.get("/api/auth/callback")
async def spotify_callback(code: Optional[str] = None, error: Optional[str] = None):
    if error or not code:
        return RedirectResponse(url=f"/?spotify_auth=error&reason={error or 'missing_code'}")

    try:
        await download_manager.process_auth_code(code)
    except Exception as e:
        return RedirectResponse(url=f"/?spotify_auth=error&reason={e}")

    return RedirectResponse(url="/?spotify_auth=success")

@app.post("/api/cancel")
async def cancel_processing():
    global cancel_requested
    cancel_requested = True
    return {"message": "Cancelando..."}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/select_folder")
def select_folder():
    try:
        if sys.platform == "darwin":
            script = 'tell application "System Events" to activate\n tell application "System Events" to return POSIX path of (choose folder)'
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            path = result.stdout.strip()
            return {"path": path} if path else {"error": "Cancelado"}
        elif sys.platform == "win32":
            script = "Add-Type -AssemblyName System.windows.forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; if ($f.ShowDialog() -eq 'OK') { Write-Output $f.SelectedPath }"
            kwargs = {'creationflags': 0x08000000} # Evita que se abra una consola negra
            result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, **kwargs)
            path = result.stdout.strip()
            return {"path": path} if path else {"error": "Cancelado"}
        else:
            return {"error": "Selección nativa no soportada. Copia y pega la ruta."}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/select_file")
def select_file():
    try:
        if sys.platform == "darwin":
            script = 'tell application "System Events" to activate\n tell application "System Events" to return POSIX path of (choose file)'
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            path = result.stdout.strip()
            return {"path": path} if path else {"error": "Cancelado"}
        elif sys.platform == "win32":
            script = "Add-Type -AssemblyName System.windows.forms; $f = New-Object System.Windows.Forms.OpenFileDialog; if ($f.ShowDialog() -eq 'OK') { Write-Output $f.FileName }"
            kwargs = {'creationflags': 0x08000000}
            result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, **kwargs)
            path = result.stdout.strip()
            return {"path": path} if path else {"error": "Cancelado"}
        else:
            return {"error": "Selección nativa no soportada. Copia y pega la ruta."}
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
async def get():
    html_content = """
    <!DOCTYPE html>
    <html class="dark" lang="es" data-theme="grafito" data-color="azul">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cicada</title>
        <link id="favicon-link" rel="icon" type="image/svg+xml" href="/static/logos/cicada_blue.svg">
        <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
        <!-- Configuración de Tailwind: variables CSS por tema/color de acento -->
        <script id="tailwind-config">
          tailwind.config = {
            darkMode: "class",
            theme: {
              extend: {
                colors: {
                  app: 'var(--bg-app)',
                  main: 'var(--bg-main)',
                  card: 'var(--bg-card)',
                  sidebar: 'var(--bg-sidebar)',
                  input: 'var(--input-bg)',
                  btn: 'var(--btn-bg)',
                  'btn-hover': 'var(--btn-hover)',
                  accent: {
                    DEFAULT: 'var(--accent)',
                    hover: 'var(--accent-hover)',
                    light: 'var(--accent-light)',
                  },
                },
                textColor: {
                  main: 'var(--text-main)',
                  muted: 'var(--text-muted)',
                  sidebar: 'var(--text-sidebar)',
                  'sidebar-muted': 'var(--text-sidebar-muted)',
                },
                borderColor: {
                  theme: 'var(--border-color)',
                },
                fontFamily: {
                  "body-sm": ["Outfit"],
                  "label-caps": ["JetBrains Mono"],
                  "headline-sm": ["Outfit"],
                  "data-lg": ["JetBrains Mono"],
                  "body-md": ["Outfit"],
                  "display-lg": ["Outfit"],
                  "headline-md": ["Outfit"],
                  "data-sm": ["JetBrains Mono"]
                },
              }
            }
          }
        </script>
        
        <style>
          /* TEMA OSCURO: GRAFITO */
          :root {
            --bg-app: #151618;
            --bg-main: #25262A;
            --bg-card: #1C1D21;
            --input-bg: #151618;
            --bg-sidebar: #F5F6F8;
            
            --btn-bg: rgba(255,255,255,0.05);
            --btn-hover: rgba(255,255,255,0.1);
            
            --text-main: #FFFFFF;
            --text-muted: #9CA3AF;
            --text-sidebar: #1A1A1A;
            --text-sidebar-muted: #6B7280;
            
            --border-color: rgba(255,255,255,0.1);
          }

          /* TEMA CLARO: ALUMINIO */
          [data-theme="aluminio"] {
            --bg-app: #D8DCE0;
            --bg-main: #E8ECEF;
            --bg-card: #FFFFFF;
            --input-bg: #F9FAFB;
            
            --btn-bg: rgba(0,0,0,0.05);
            --btn-hover: rgba(0,0,0,0.1);
            
            --text-main: #1A1A1A;
            --text-muted: #6B7280;
            
            --border-color: rgba(0,0,0,0.1);
          }

          /* COLORES DE ACENTO */
          [data-color="azul"] { --accent: #0099FF; --accent-hover: #0088e6; --accent-light: rgba(0, 153, 255, 0.15); }
          [data-color="verde"] { --accent: #77C800; --accent-hover: #6ab300; --accent-light: rgba(119, 200, 0, 0.15); }
          [data-color="morado"] { --accent: #8A2BE2; --accent-hover: #7b27c9; --accent-light: rgba(138, 43, 226, 0.15); }
          [data-color="naranja"] { --accent: #FF8800; --accent-hover: #e67a00; --accent-light: rgba(255, 136, 0, 0.15); }
          [data-color="rosa"] { --accent: #E62E6B; --accent-hover: #cc295f; --accent-light: rgba(230, 46, 107, 0.15); }

          /* LOGO DE CICADA: se muestra la variante que coincide con el color de acento activo */
          .cicada-logo-img { display: none; }
          [data-color="azul"] .cicada-logo-img[data-logo-color="azul"],
          [data-color="verde"] .cicada-logo-img[data-logo-color="verde"],
          [data-color="morado"] .cicada-logo-img[data-logo-color="morado"],
          [data-color="naranja"] .cicada-logo-img[data-logo-color="naranja"],
          [data-color="rosa"] .cicada-logo-img[data-logo-color="rosa"] { display: block; }
        </style>
        <style>
            body {
                background-color: #0b0c10;
                color: #e3e2e8;
                overflow: hidden;
            }

            .glass-card {
                background: rgba(31, 38, 57, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(16px);
                border-radius: 12px;
            }

            .custom-scrollbar::-webkit-scrollbar {
                width: 4px;
            }
            .custom-scrollbar::-webkit-scrollbar-track {
                background: rgba(255, 255, 255, 0.02);
            }
            .custom-scrollbar::-webkit-scrollbar-thumb {
                background: rgba(255, 255, 255, 0.1);
            }

            @keyframes scanline {
                0% { transform: translateY(-100%); }
                100% { transform: translateY(100%); }
            }
            .scanline-effect {
                position: relative;
                overflow: hidden;
            }
            .scanline-effect::after {
                content: "";
                position: absolute;
                top: 0; left: 0; right: 0; bottom: 0;
                background: linear-gradient(to bottom, transparent, rgba(6, 182, 212, 0.03), transparent);
                height: 100%;
                animation: scanline 6s linear infinite;
                pointer-events: none;
            }

            .nav-item-active {
                border-left: 2px solid #10b981;
                box-shadow: -4px 0 12px rgba(16, 185, 129, 0.3);
                background: rgba(255, 255, 255, 0.05);
                color: #1a1b20 !important;
            }
            .nav-item-inactive {
                color: rgba(26, 27, 32, 0.4);
            }
            .nav-item:hover {
                background: rgba(0, 0, 0, 0.05);
            }

            /* --- Vistas (PROCESS / SPOTIFY / PLAYLISTS / LIBRARY) --- */
            .view { display: none; }
            #view-process.active { display: grid; }
            #view-spotify.active { display: flex; }
            #view-playlists.active { display: grid; }
            #view-library.active { display: flex; }

            .cicada-checkbox {
                width: 16px;
                height: 16px;
                accent-color: #10b981;
                cursor: pointer;
                flex-shrink: 0;
            }

            .library-group-btn, .lang-btn {
                background: var(--btn-bg);
                color: var(--text-muted);
                transition: background 0.2s, color 0.2s;
            }
            .library-group-btn:hover, .lang-btn:hover {
                background: var(--btn-hover);
                color: var(--text-main);
            }
            .library-group-btn.active, .lang-btn.active {
                background: var(--accent-light);
                color: var(--accent);
            }

            details.library-group > summary {
                list-style: none;
                cursor: pointer;
            }
            details.library-group > summary::-webkit-details-marker {
                display: none;
            }
            details.library-group > summary::before {
                content: "▸ ";
                color: rgba(255, 255, 255, 0.3);
            }
            details.library-group[open] > summary::before {
                content: "▾ ";
            }

            .cicada-input {
                background: var(--input-bg) !important;
                border: none !important;
                border-bottom: 1px solid var(--border-color) !important;
                border-radius: 8px !important;
                font-family: 'JetBrains Mono', monospace;
                color: var(--text-main) !important;
                outline: none;
                box-shadow: none !important;
                transition: border-color 0.2s ease;
            }
            .cicada-input:focus {
                border-color: var(--accent) !important;
            }
            .cicada-input::placeholder {
                color: var(--text-muted);
            }
        </style>
    </head>
    <body class="bg-app text-main font-body-md text-body-md h-screen flex justify-center p-4">
        <div class="app-shell w-full h-full max-w-[1920px] mx-auto flex gap-4">
        <!-- Barra de navegación lateral -->
        <aside class="h-full w-[100px] bg-sidebar rounded-[20px] flex flex-col items-center py-8 z-50 text-sidebar">
            <div class="mb-12">
                <div class="relative w-14 h-14 rounded-2xl overflow-hidden cursor-pointer hover:opacity-70 transition-opacity" onclick="openAbout()" title="Sobre Cicada" data-i18n-title="about_tooltip">
                    <img src="/static/logos/cicada_blue.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="azul" alt="Cicada">
                    <img src="/static/logos/cicada_green.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="verde" alt="Cicada">
                    <img src="/static/logos/cicada_purple.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="morado" alt="Cicada">
                    <img src="/static/logos/cicada_orange.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="naranja" alt="Cicada">
                    <img src="/static/logos/cicada_pink.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="rosa" alt="Cicada">
                </div>
            </div>
            <nav class="flex-1 w-full flex flex-col items-stretch gap-4">
                <button type="button" class="nav-item nav-item-active flex flex-col items-center py-4 transition-all w-full" data-view="process" onclick="showView('process')">
                    <span class="material-symbols-outlined text-[24px] mb-1" style="font-variation-settings: 'FILL' 1;">terminal</span>
                    <span class="font-label-caps text-[11px]" data-i18n="nav_metadata">Metadatos</span>
                </button>
                <button type="button" class="nav-item nav-item-inactive flex flex-col items-center py-4 transition-all w-full" data-view="spotify" onclick="showView('spotify')">
                    <span class="material-symbols-outlined text-[24px] mb-1">queue_music</span>
                    <span class="font-label-caps text-[11px]" data-i18n="nav_download">Descarga</span>
                </button>
                <button type="button" class="nav-item nav-item-inactive flex flex-col items-center py-4 transition-all w-full" data-view="playlists" onclick="showView('playlists'); loadSpotifyPlaylists();">
                    <span class="material-symbols-outlined text-[24px] mb-1">playlist_play</span>
                    <span class="font-label-caps text-[11px]" data-i18n="nav_playlist">Playlist</span>
                </button>
                <button type="button" class="nav-item nav-item-inactive flex flex-col items-center py-4 transition-all w-full" data-view="library" onclick="showView('library')">
                    <span class="material-symbols-outlined text-[24px] mb-1">library_music</span>
                    <span class="font-label-caps text-[11px]" data-i18n="nav_library">Biblioteca</span>
                </button>
            </nav>
            <div class="mt-auto flex flex-col items-center gap-6">
                <button type="button" onclick="openSettings()" class="material-symbols-outlined text-sidebar/60 hover:text-sidebar transition-colors" data-i18n-title="settings_tooltip" title="Ajustes">settings</button>
                <div class="relative w-10 h-10 rounded-xl bg-black/10 dark:bg-black/20 flex items-center justify-center border-2 border-transparent" data-i18n-title="connection_tooltip" title="Estado de conexión">
                    <span class="material-symbols-outlined text-[22px] text-sidebar/60">graphic_eq</span>
                    <span id="ws-status-dot" class="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-gray-400 border-2 border-sidebar"></span>
                </div>
            </div>
        </aside>

        <!-- Modal de Ajustes -->
        <div id="settings-modal" class="hidden fixed inset-0 z-[100] items-center justify-center bg-black/60 backdrop-blur-sm">
            <div class="w-full max-w-lg mx-4 p-6 flex flex-col gap-4 max-h-[85vh] overflow-y-auto custom-scrollbar rounded-2xl border border-theme bg-card">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-accent text-[22px]">settings</span>
                        <span class="font-label-caps text-[14px] tracking-widest text-main" data-i18n="settings_title">Ajustes</span>
                    </div>
                    <button type="button" onclick="closeSettings()" class="material-symbols-outlined text-muted/60 hover:text-main transition-colors">close</button>
                </div>

                <div class="flex flex-col gap-2">
                    <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_language_title">Idioma</span>
                    <div class="flex gap-2">
                        <button type="button" class="lang-btn flex-1 py-2 rounded-lg font-label-caps text-[11px] transition-colors" data-lang="es" onclick="applyLanguage('es')">Español</button>
                        <button type="button" class="lang-btn flex-1 py-2 rounded-lg font-label-caps text-[11px] transition-colors" data-lang="en" onclick="applyLanguage('en')">English</button>
                        <button type="button" class="lang-btn flex-1 py-2 rounded-lg font-label-caps text-[11px] transition-colors" data-lang="ja" onclick="applyLanguage('ja')">日本語</button>
                    </div>
                </div>

                <div class="flex flex-col gap-2 border-t border-theme pt-3">
                    <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_spotify_title">Cuenta de Spotify</span>
                    <div class="flex items-center justify-between gap-2">
                        <span id="settings-spotify-status" class="font-data-sm text-[13px] text-muted/60" data-i18n="settings_spotify_not_connected">No conectado a Spotify</span>
                        <button type="button" onclick="window.location.href='/api/auth/login'" id="settings-spotify-connect-btn" class="px-3 py-2 rounded-lg bg-accent text-white font-label-caps text-[11px] hover:brightness-110 transition-all whitespace-nowrap" data-i18n="settings_spotify_connect_btn">Conectar con Spotify</button>
                    </div>
                </div>

                <div class="flex flex-col gap-2 border-t border-theme pt-3">
                    <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_credentials_title">Claves de Acceso</span>

                    <label class="font-label-caps text-[10px] text-muted/50" data-i18n="settings_acoustid_label">Clave de AcoustID</label>
                    <div class="flex gap-2">
                        <input type="password" id="settings_acoustid_key" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]" placeholder="Client key de AcoustID"/>
                        <button type="button" onclick="toggleSecretVisibility('settings_acoustid_key', this)" class="material-symbols-outlined text-[18px] text-muted/50 hover:text-accent px-2">visibility</button>
                    </div>

                    <label class="font-label-caps text-[10px] text-muted/50" data-i18n="settings_spotify_id_label">ID de Cliente de Spotify</label>
                    <div class="flex gap-2">
                        <input type="password" id="settings_spotify_id" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]" placeholder="Client ID de Spotify"/>
                        <button type="button" onclick="toggleSecretVisibility('settings_spotify_id', this)" class="material-symbols-outlined text-[18px] text-muted/50 hover:text-accent px-2">visibility</button>
                    </div>

                    <label class="font-label-caps text-[10px] text-muted/50" data-i18n="settings_spotify_secret_label">Clave Secreta de Spotify</label>
                    <div class="flex gap-2">
                        <input type="password" id="settings_spotify_secret" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]" placeholder="Client Secret de Spotify"/>
                        <button type="button" onclick="toggleSecretVisibility('settings_spotify_secret', this)" class="material-symbols-outlined text-[18px] text-muted/50 hover:text-accent px-2">visibility</button>
                    </div>
                </div>

                <div class="flex flex-col gap-2 border-t border-theme pt-3">
                    <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_identification_title">Identificación de Canciones</span>
                    <label class="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" id="settings_plan_c_enabled" class="cicada-checkbox"/>
                        <span class="font-data-sm text-[13px] text-muted/70" data-i18n="settings_plan_c_label">Adivinar por el nombre del archivo cuando no se reconoce la canción</span>
                    </label>
                    <p class="font-data-sm text-[11px] text-muted/40 pl-6" data-i18n="settings_plan_c_hint">Apagado por defecto: suele ser poco preciso. Si está apagado, esos archivos se reportan como error en vez de adivinar el título/artista.</p>
                </div>

                
                                <div class="flex flex-col gap-4 border-t border-theme pt-5">
                    <!-- TEMA -->
                    <div class="flex flex-col gap-2">
                        <span class="font-label-caps text-[12px] text-muted tracking-widest font-bold" data-i18n="settings_theme_title">TEMA</span>
                        <div class="flex gap-3">
                            <button type="button" class="theme-btn flex-1 py-3 rounded-xl border-2 font-label-caps text-[13px] font-bold transition-all" data-theme-val="grafito" onclick="selectThemeUI('grafito')" data-i18n="settings_theme_dark">Grafito</button>
                            <button type="button" class="theme-btn flex-1 py-3 rounded-xl border-2 font-label-caps text-[13px] font-bold transition-all" data-theme-val="aluminio" onclick="selectThemeUI('aluminio')" data-i18n="settings_theme_light">Aluminio</button>
                        </div>
                        <input type="hidden" id="settings_theme" value="grafito">
                    </div>

                    <!-- COLOR NANO -->
                    <div class="flex flex-col gap-2 mt-2">
                        <span class="font-label-caps text-[12px] text-muted tracking-widest font-bold" data-i18n="settings_color_title">COLOR NANO</span>
                        <div class="flex gap-4 items-center">
                            <button type="button" class="color-btn w-8 h-8 rounded-full transition-all flex items-center justify-center relative" style="background-color: #0099FF;" data-color-val="azul" onclick="selectColorUI('azul')"></button>
                            <button type="button" class="color-btn w-8 h-8 rounded-full transition-all flex items-center justify-center relative" style="background-color: #77C800;" data-color-val="verde" onclick="selectColorUI('verde')"></button>
                            <button type="button" class="color-btn w-8 h-8 rounded-full transition-all flex items-center justify-center relative" style="background-color: #8A2BE2;" data-color-val="morado" onclick="selectColorUI('morado')"></button>
                            <button type="button" class="color-btn w-8 h-8 rounded-full transition-all flex items-center justify-center relative" style="background-color: #FF8800;" data-color-val="naranja" onclick="selectColorUI('naranja')"></button>
                            <button type="button" class="color-btn w-8 h-8 rounded-full transition-all flex items-center justify-center relative" style="background-color: #E62E6B;" data-color-val="rosa" onclick="selectColorUI('rosa')"></button>
                        </div>
                        <input type="hidden" id="settings_color" value="azul">
                    </div>
                </div>

<div class="flex flex-col gap-2 border-t border-theme pt-3">
                    <span class="font-label-caps text-[11px] text-accent/70" data-i18n="settings_folders_title">Carpetas Predeterminadas</span>

                    <label class="font-label-caps text-[10px] text-muted/50" data-i18n="settings_library_dir_label">Carpeta de tu Biblioteca</label>
                    <div class="flex gap-2">
                        <input type="text" id="settings_library_dir" placeholder="/Users/usuario/Musica/Organizada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                        <button type="button" onclick="pickFolder('settings_library_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                    </div>

                    <label class="font-label-caps text-[10px] text-muted/50" data-i18n="settings_input_dir_label">Carpeta de Origen (Metadatos)</label>
                    <div class="flex gap-2">
                        <input type="text" id="settings_process_input_dir" placeholder="/Users/usuario/Musica/Entrada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                        <button type="button" onclick="pickFolder('settings_process_input_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                    </div>

                    <label class="font-label-caps text-[10px] text-muted/50" data-i18n="settings_output_dir_label">Carpeta de Destino (Metadatos)</label>
                    <div class="flex gap-2">
                        <input type="text" id="settings_process_output_dir" placeholder="/Users/usuario/Musica/Organizada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                        <button type="button" onclick="pickFolder('settings_process_output_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                    </div>
                </div>

                <div class="flex gap-2 justify-end items-center pt-2">
                    <span id="settings-status" class="font-data-sm text-[12px] text-secondary mr-auto"></span>
                    <button type="button" onclick="closeSettings()" class="px-4 py-2 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[12px] transition-colors" data-i18n="common_cancel">Cancelar</button>
                    <button type="button" id="settingsSaveBtn" onclick="saveSettings()" class="px-4 py-2 rounded-lg bg-accent text-white font-label-caps text-[12px] hover:brightness-110 transition-all" data-i18n="common_save">Guardar</button>
                </div>
            </div>
        </div>

        <!-- Modal de Sobre / About -->
        <div id="about-modal" class="hidden fixed inset-0 z-[100] items-center justify-center bg-black/60 backdrop-blur-sm">
            <div class="w-full max-w-sm mx-4 p-6 flex flex-col items-center gap-3 rounded-2xl border border-theme bg-card text-center">
                <button type="button" onclick="closeAbout()" class="material-symbols-outlined text-muted/60 hover:text-main transition-colors self-end -mb-2 -mt-2 -mr-2">close</button>

                <div class="relative w-16 h-16 rounded-2xl bg-sidebar flex items-center justify-center overflow-hidden">
                    <img src="/static/logos/cicada_blue.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="azul" alt="Cicada">
                    <img src="/static/logos/cicada_green.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="verde" alt="Cicada">
                    <img src="/static/logos/cicada_purple.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="morado" alt="Cicada">
                    <img src="/static/logos/cicada_orange.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="naranja" alt="Cicada">
                    <img src="/static/logos/cicada_pink.svg" class="cicada-logo-img absolute inset-0 w-full h-full object-cover" data-logo-color="rosa" alt="Cicada">
                </div>

                <span class="font-display-lg text-[20px] font-bold tracking-tighter text-main">Cicada</span>
                <span class="font-label-caps text-[11px] text-secondary" id="about-version" data-i18n="about_version">Versión 1.0.1</span>

                <p class="font-data-sm text-[13px] text-muted/70" data-i18n="about_description">Herramienta local de organización musical y sincronización automática de metadatos de alta fidelidad.</p>

                <div class="w-full border-t border-theme my-1"></div>

                <p class="font-data-sm text-[13px] text-muted/70"><span data-i18n="about_author_label">Desarrollado por</span> <b>JJaroll</b></p>
                <p class="font-data-sm text-[11px] text-muted/40" data-i18n="about_license">Distribuido bajo Licencia GNU GPLv3</p>

                <button type="button" onclick="window.open('https://github.com/JJaroll', '_blank')" class="mt-2 w-full px-4 py-2 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors inline-flex items-center justify-center gap-1.5">
                    <span class="material-symbols-outlined text-[16px]">code</span>
                    <span data-i18n="about_github_btn">Ver en GitHub</span>
                </button>
            </div>
        </div>

        <!-- Main Canvas: contenido por pestaña (izquierda) + módulo de proceso persistente (derecha) -->
        <main class="flex-1 h-full overflow-hidden flex gap-4">
            <div class="flex-1 h-full overflow-hidden">

                <!-- Vista: Metadatos -->
                <div id="view-process" class="view active grid-cols-9 grid-rows-6 gap-4 h-full overflow-hidden">
                    <div class="col-start-1 col-span-3 row-start-1 row-span-3 glass-card p-5 flex flex-col gap-3 overflow-y-auto custom-scrollbar">
                        <div class="flex items-center gap-2 mb-1">
                            <span class="material-symbols-outlined text-accent text-[20px]">settings_input_component</span>
                            <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="process_folders_title">Carpetas de Trabajo</span>
                        </div>

                        <div class="flex flex-col gap-1.5">
                            <label for="input_dir" class="font-label-caps text-[10px] text-accent/70" data-i18n="process_source_label">Carpeta de Origen</label>
                            <div class="flex gap-2">
                                <input type="text" id="input_dir" placeholder="/Users/usuario/Musica/Entrada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                                <button type="button" onclick="pickFolder('input_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                            </div>
                        </div>

                        <div class="flex flex-col gap-1.5">
                            <label for="output_dir" class="font-label-caps text-[10px] text-accent/70" data-i18n="process_dest_label">Carpeta de Destino</label>
                            <div class="flex gap-2">
                                <input type="text" id="output_dir" placeholder="/Users/usuario/Musica/Organizada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                                <button type="button" onclick="pickFolder('output_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                            </div>
                        </div>

                        <div class="flex gap-2 mt-1">
                            <button id="startBtn" type="button" onclick="startProcess()" class="flex-1 py-3 bg-accent text-white rounded-xl font-label-caps text-[12px] tracking-widest hover:brightness-110 transition-all inline-flex items-center justify-center gap-1.5">
                                <span class="material-symbols-outlined text-[18px]">play_arrow</span> <span data-i18n="process_start_btn">Iniciar</span>
                            </button>
                            <button id="cancelBtnSource" type="button" onclick="cancelProcess()" class="cancel-action hidden py-3 px-3 bg-red-600 text-white rounded-xl font-label-caps text-[12px] tracking-widest hover:brightness-110 transition-all inline-flex items-center justify-center gap-1.5">
                                <span class="material-symbols-outlined text-[18px]">stop</span> <span data-i18n="process_cancel_btn">Cancelar</span>
                            </button>
                        </div>
                    </div>

                    <!-- Actividad Reciente -->
                    <div class="col-start-1 col-span-3 row-start-4 row-span-3 glass-card p-5 flex flex-col">
                        <div class="flex items-center justify-between mb-3">
                            <div class="flex items-center gap-2">
                                <span class="material-symbols-outlined text-accent text-[20px]">inventory_2</span>
                                <span class="font-label-caps text-[11px] tracking-widest text-muted/60" data-i18n="process_recent_activity_title">Actividad Reciente</span>
                            </div>
                            <span class="font-label-caps text-[10px] text-secondary cursor-pointer" onclick="showView('library')" data-i18n="process_view_more">Ver más</span>
                        </div>
                        <div class="flex flex-col gap-2 overflow-y-auto custom-scrollbar flex-1" id="process-file-grid">
                            <p class="font-data-sm text-[13px] text-muted/40" data-i18n="process_no_files_yet">Todavía no se procesó ningún archivo en esta sesión.</p>
                        </div>
                    </div>

                    <!-- Estadísticas en vivo -->
                    <div class="col-start-4 col-span-3 row-start-1 row-span-1 glass-card p-6 flex flex-col justify-center">
                        <span class="font-label-caps text-label-caps text-muted/60" data-i18n="process_progress_title">Progreso</span>
                        <div class="flex items-baseline gap-2 mt-1">
                            <span class="font-data-lg text-[28px] text-main" id="stat-progress-count">0/0</span>
                            <span class="font-data-sm text-secondary text-[12px] uppercase" id="stat-progress-pct">0%</span>
                        </div>
                    </div>
                    <div class="col-start-7 col-span-3 row-start-1 row-span-1 glass-card p-6 flex flex-col justify-center">
                        <span class="font-label-caps text-label-caps text-muted/60" data-i18n="process_connection_title">Conexión</span>
                        <div class="flex items-center justify-between mt-1">
                            <span class="font-data-lg text-[22px] text-accent" id="stat-ws-status" data-i18n="ws_connecting_short">Conectando</span>
                        </div>
                    </div>

                    <!-- Centro: registro de actividad en vivo -->
                    <div class="col-start-4 col-span-6 row-start-2 row-span-5 glass-card relative overflow-hidden scanline-effect">
                        <div class="absolute top-0 left-0 right-0 p-5 flex justify-between items-center z-10 bg-gradient-to-b from-black/40 to-transparent">
                            <div class="flex items-center gap-3">
                                <span class="material-symbols-outlined text-secondary text-[22px]">analytics</span>
                                <span class="font-label-caps text-[13px] tracking-[0.2em] text-main" data-i18n="process_activity_log_title">Registro de Actividad</span>
                            </div>
                            <span class="font-data-sm text-[12px] text-secondary/60" id="ws-status-label" data-i18n="ws_connecting_dots">Conectando...</span>
                        </div>
                        <div class="absolute inset-0 p-6 pt-16 font-data-sm text-[13px] leading-relaxed custom-scrollbar overflow-y-auto" id="log-container">
                            <p class="text-secondary/60">&gt; <span data-i18n="process_log_ready">Listo. Esperando instrucciones...</span></p>
                        </div>
                    </div>
                </div>

                <!-- Vista: Descarga -->
                <div id="view-spotify" class="view h-full flex-col gap-4 overflow-hidden">
                    <div class="glass-card p-5 flex flex-col gap-3">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-accent text-[20px]">link</span>
                            <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="spotify_link_title">Enlace de Spotify</span>
                        </div>
                        <div class="flex gap-2">
                            <input type="text" id="spotify_url" placeholder="https://open.spotify.com/track|album|playlist/..." class="cicada-input flex-1 rounded-lg px-3 py-3 text-[15px]"/>
                            <button type="button" id="resolveBtn" onclick="resolveSpotifyUrl()" class="px-5 rounded-lg bg-accent text-white font-label-caps text-[12px] hover:brightness-110 transition-all inline-flex items-center gap-1.5">
                                <span class="material-symbols-outlined text-[18px]">search</span> <span data-i18n="spotify_analyze_btn">Analizar</span>
                            </button>
                        </div>
                        <p id="spotify-resolve-status" class="font-data-sm text-[12px] text-[#f43f5e]"></p>
                    </div>

                    <div class="glass-card p-5 flex flex-col gap-2">
                        <label for="spotify_output_dir" class="font-label-caps text-[11px] text-accent/70" data-i18n="process_dest_label">Carpeta de Destino</label>
                        <div class="flex gap-2">
                            <input type="text" id="spotify_output_dir" placeholder="/Users/usuario/Musica/Organizada" class="cicada-input flex-1 rounded-lg px-3 py-3 text-[15px]"/>
                            <button type="button" onclick="pickFolder('spotify_output_dir')" class="px-4 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[12px] transition-colors" data-i18n="common_choose">Elegir</button>
                        </div>
                    </div>

                    <div class="glass-card p-5 flex flex-col flex-1 overflow-hidden">
                        <div class="flex items-center justify-between mb-3">
                            <div class="flex items-center gap-2">
                                <span class="material-symbols-outlined text-accent text-[20px]">queue_music</span>
                                <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="spotify_tracks_found_title">Canciones Encontradas</span>
                                <span class="font-data-sm text-[12px] text-muted/40" id="spotify-track-count"></span>
                            </div>
                            <label class="flex items-center gap-2 font-label-caps text-[11px] text-muted/60 cursor-pointer">
                                <input type="checkbox" id="spotify-select-all" onchange="toggleSelectAllTracks(this.checked)" class="cicada-checkbox"/>
                                <span data-i18n="spotify_select_all">Seleccionar Todas</span>
                            </label>
                        </div>
                        <div class="flex flex-col gap-2 overflow-y-auto custom-scrollbar flex-1" id="spotify-track-list">
                            <p class="font-data-sm text-[13px] text-muted/40" data-i18n="spotify_hint_paste_link">Pega un link de Spotify (canción, álbum o playlist) y presiona Analizar para ver las canciones.</p>
                        </div>
                        <button type="button" id="spotifyDownloadBtn" onclick="startSpotifyDownload()" disabled class="mt-3 w-full py-3 bg-accent text-white rounded-xl font-label-caps text-[13px] tracking-widest hover:brightness-110 transition-all inline-flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed">
                            <span class="material-symbols-outlined text-[18px]">download</span> <span data-i18n="spotify_download_selected_btn">Descargar Seleccionadas</span> (<span id="spotify-selected-count">0</span>)
                        </button>
                    </div>
                </div>

                <!-- Vista: Playlists -->
                <div id="view-playlists" class="view grid-cols-12 grid-rows-6 gap-4 h-full overflow-hidden">
                    <!-- Izquierda: playlists del usuario -->
                    <div class="col-start-1 col-span-3 row-start-1 row-span-6 glass-card p-5 flex flex-col gap-3 overflow-hidden">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="material-symbols-outlined text-accent text-[20px]">playlist_play</span>
                                <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="playlists_my_playlists_title">Mis Playlists</span>
                            </div>
                            <button type="button" onclick="loadSpotifyPlaylists()" data-i18n-title="process_view_more" title="Recargar" class="material-symbols-outlined text-[18px] text-muted/50 hover:text-accent transition-colors">refresh</button>
                        </div>
                        <div class="flex flex-col gap-2 overflow-y-auto custom-scrollbar flex-1" id="playlists-list">
                            <p class="font-data-sm text-[13px] text-muted/40" data-i18n="playlists_loading">Cargando tus playlists...</p>
                        </div>
                    </div>

                    <!-- Centro: canciones de la playlist seleccionada + configuración para replicar -->
                    <div class="col-start-4 col-span-3 row-start-1 row-span-6 glass-card p-5 flex flex-col gap-3 overflow-hidden">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-accent text-[20px]">queue_music</span>
                            <span class="font-label-caps text-[12px] tracking-widest text-muted/60" id="playlist-detail-title" data-i18n="playlists_choose_title">Elige una playlist</span>
                        </div>

                        <div class="flex-col gap-2" id="replicate-controls" style="display:none">
                            <label for="library_dir" class="font-label-caps text-[10px] text-accent/70" data-i18n="playlists_local_library_label">Tu Biblioteca Local</label>
                            <div class="flex gap-2">
                                <input type="text" id="library_dir" placeholder="/Users/usuario/Musica/Organizada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                                <button type="button" onclick="pickFolder('library_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                            </div>
                            <button type="button" id="replicateBtn" onclick="replicatePlaylist()" class="w-full py-2 bg-accent text-white rounded-lg font-label-caps text-[11px] hover:brightness-110 transition-all inline-flex items-center justify-center gap-1.5">
                                <span class="material-symbols-outlined text-[18px]">content_copy</span> <span data-i18n="playlists_replicate_btn">Replicar Playlist</span>
                            </button>
                        </div>

                        <div class="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-2" id="playlist-track-list">
                            <p class="font-data-sm text-[13px] text-muted/40" data-i18n="playlists_choose_hint">Elige una playlist de la izquierda para ver sus canciones.</p>
                        </div>
                    </div>

                    <!-- Vista Previa de la Playlist -->
                    <div class="col-start-7 col-span-6 row-start-1 row-span-6 glass-card p-5 flex flex-col gap-2 overflow-hidden">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="material-symbols-outlined text-accent text-[20px]">save</span>
                                <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="playlists_preview_title">Vista Previa de la Playlist</span>
                            </div>
                            <span class="font-data-sm text-[12px] text-muted/40" id="replicate-match-summary"></span>
                        </div>
                        <p class="font-data-sm text-[12px] text-muted/40" id="replicate-empty-hint" data-i18n="playlists_preview_hint">Elige una playlist y presiona Replicar Playlist para armar aquí la vista previa. Vas a poder arrastrar las canciones para reordenarlas y destildar las que no quieras incluir.</p>
                        <div class="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-2" id="replicate-track-list"></div>
                        <div class="hidden gap-2 items-center mt-1" id="generate-m3u8-controls">
                            <input type="text" id="m3u8_name" placeholder="Nombre de la playlist" data-i18n-placeholder="playlists_m3u8_name_placeholder" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                            <button type="button" id="generateM3u8Btn" onclick="generatePlaylistM3u8()" class="px-4 py-2 bg-gray-600 text-white rounded-lg font-label-caps text-[12px] hover:brightness-110 transition-all inline-flex items-center gap-1.5">
                                <span class="material-symbols-outlined text-[18px]">save</span> <span data-i18n="playlists_generate_btn">Generar Playlist</span>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Vista: Biblioteca -->
                <div id="view-library" class="view h-full flex-col gap-4">
                    <div class="glass-card p-5 flex flex-col gap-3">
                        <div class="flex items-center gap-2">
                            <span class="material-symbols-outlined text-accent text-[20px]">library_music</span>
                            <span class="font-label-caps text-[12px] tracking-widest text-muted/60" data-i18n="library_my_library_title">Mi Biblioteca</span>
                        </div>
                        <div class="flex gap-2">
                            <input type="text" id="library_browse_dir" placeholder="/Users/usuario/Musica/Organizada" class="cicada-input flex-1 rounded-lg px-3 py-2 text-[14px]"/>
                            <button type="button" onclick="pickFolder('library_browse_dir')" class="px-3 rounded-lg bg-btn hover:bg-btn-hover font-label-caps text-[11px] transition-colors" data-i18n="common_choose">Elegir</button>
                            <button type="button" onclick="saveLibraryDirAndScan()" class="px-4 rounded-lg bg-accent text-white font-label-caps text-[11px] hover:brightness-110 transition-all" data-i18n="library_save_scan_btn">Guardar y Buscar Canciones</button>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="font-label-caps text-[11px] text-muted/50" data-i18n="library_group_by_label">Agrupar por</span>
                            <button type="button" class="library-group-btn active px-3 py-1 rounded-full font-label-caps text-[11px] transition-colors" data-group="all" onclick="setLibraryGrouping('all')" data-i18n="library_group_all">Todas</button>
                            <button type="button" class="library-group-btn px-3 py-1 rounded-full font-label-caps text-[11px] transition-colors" data-group="artist" onclick="setLibraryGrouping('artist')" data-i18n="library_group_artist">Artista</button>
                            <button type="button" class="library-group-btn px-3 py-1 rounded-full font-label-caps text-[11px] transition-colors" data-group="album" onclick="setLibraryGrouping('album')" data-i18n="library_group_album">Álbum</button>
                            <button type="button" class="library-group-btn px-3 py-1 rounded-full font-label-caps text-[11px] transition-colors" data-group="playlist" onclick="setLibraryGrouping('playlist')" data-i18n="library_group_playlist">Playlist</button>
                            <span class="ml-auto font-data-sm text-[12px] text-muted/40" id="library-track-count"></span>
                        </div>
                    </div>
                    <div class="glass-card p-5 flex-1 overflow-y-auto custom-scrollbar">
                        <div class="flex flex-col gap-1" id="library-browser">
                            <p class="font-data-sm text-[13px] text-muted/40" data-i18n="library_configure_hint">Configura la carpeta de tu biblioteca arriba para verla aquí.</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Módulo derecho: Progreso (Metadatos/Descarga) o Reproductor (Biblioteca). Oculto en Playlist. -->
            <div id="process-module" class="w-[320px] flex-shrink-0 h-full bg-sidebar rounded-[24px] p-6 flex flex-col gap-6 text-sidebar">
                <div id="progress-panel" class="flex flex-col gap-6 h-full">
                    <div class="flex justify-between items-center">
                        <span id="status-pill" class="bg-accent-light text-accent px-3 py-1 rounded-full font-label-caps text-[12px]">En espera</span>
                        <span class="font-data-sm text-[12px] text-sidebar/40" data-i18n="player_cicada_label">Cicada</span>
                    </div>
                    <div class="flex-1 flex flex-col justify-center items-center text-center">
                        <div class="w-full aspect-square rounded-[20px] overflow-hidden shadow-2xl mb-8 relative border-4 border-transparent bg-black/5 dark:bg-black/10 flex items-center justify-center">
                            <div class="flex flex-col items-center gap-2 text-sidebar/30" id="coverPlaceholder">
                                <span class="material-symbols-outlined text-[40px]">music_note</span>
                                <span class="font-label-caps text-[11px]" data-i18n="player_no_cover">Sin carátula</span>
                            </div>
                            <img alt="Album Art" class="w-full h-full object-cover absolute inset-0 hidden" id="currentCover" src=""/>
                        </div>
                        <h2 class="font-headline-sm text-[20px] leading-tight mb-1 truncate w-full" id="track-title">En espera...</h2>
                        <p class="font-body-sm text-sidebar/60 mb-8 truncate w-full" id="track-subtitle">Configura una fuente para comenzar</p>
                        <div class="w-full space-y-4">
                            <div class="w-full h-[54px] bg-black/5 dark:bg-black/10 rounded-xl p-3 flex items-center justify-between">
                                <span class="font-label-caps text-[11px] text-sidebar/40 uppercase" data-i18n="player_remaining_time_label">Tiempo Restante</span>
                                <span class="font-data-lg text-accent text-[16px]" id="eta_display">&#45;&#45;</span>
                            </div>
                            <div class="relative w-full h-1.5 bg-black/10 dark:bg-black/20 rounded-full overflow-hidden">
                                <div class="absolute inset-y-0 left-0 bg-accent w-0 transition-all duration-500" id="bar"></div>
                            </div>
                            <div class="flex justify-between font-data-sm text-[12px] text-sidebar/40">
                                <span data-i18n="player_progress_label">Avance</span>
                                <span id="progress_label">0%</span>
                            </div>
                        </div>
                    </div>
                    <button id="cancelBtnProcess" type="button" onclick="cancelProcess()" class="cancel-action hidden w-full py-4 bg-card text-main rounded-xl font-label-caps tracking-widest hover:bg-black transition-colors items-center justify-center gap-2">
                        <span class="material-symbols-outlined text-sm">stop_circle</span> <span data-i18n="player_cancel_process_btn">Cancelar Proceso</span>
                    </button>
                </div>

                <div id="player-panel" class="hidden flex flex-col gap-6 h-full">
                    <div class="flex justify-between items-center">
                        <span class="font-label-caps text-[12px] text-sidebar/40" data-i18n="player_title">Reproductor</span>
                        <span class="font-data-sm text-[12px] text-sidebar/40" data-i18n="player_cicada_label">Cicada</span>
                    </div>
                    <div class="flex-1 flex flex-col justify-center items-center text-center">
                        <div class="w-full aspect-square rounded-[20px] overflow-hidden shadow-2xl mb-8 relative border-4 border-transparent bg-black/5 dark:bg-black/10 flex items-center justify-center">
                            <div class="flex flex-col items-center gap-2 text-sidebar/30" id="playerCoverPlaceholder">
                                <span class="material-symbols-outlined text-[40px]">music_note</span>
                                <span class="font-label-caps text-[11px]" data-i18n="player_no_cover">Sin carátula</span>
                            </div>
                            <img alt="Cover" class="w-full h-full object-cover absolute inset-0 hidden" id="playerCover" src=""/>
                        </div>
                        <h2 class="font-headline-sm text-[20px] leading-tight mb-1 truncate w-full" id="playerTrackTitle">Nada sonando</h2>
                        <p class="font-body-sm text-sidebar/60 mb-8 truncate w-full" id="playerTrackArtist">Elige una canción de tu biblioteca</p>
                        <div class="w-full space-y-3">
                            <div class="relative w-full h-1.5 bg-black/10 dark:bg-black/20 rounded-full overflow-hidden cursor-pointer" id="playerSeekTrack" onclick="seekPlayer(event)">
                                <div class="absolute inset-y-0 left-0 bg-accent w-0" id="playerSeekFill"></div>
                            </div>
                            <div class="flex justify-between font-data-sm text-[12px] text-sidebar/40">
                                <span id="playerCurrentTime">0:00</span>
                                <span id="playerDuration">0:00</span>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center justify-center gap-4">
                        <button type="button" id="btnShuffle" onclick="toggleShuffle()" class="material-symbols-outlined text-[20px] text-sidebar/40 hover:text-sidebar transition-colors">shuffle</button>
                        <button type="button" onclick="playPrevTrack()" class="material-symbols-outlined text-[24px] text-sidebar/70 hover:text-sidebar">skip_previous</button>
                        <button type="button" id="playerPlayPauseBtn" onclick="togglePlayPause()" class="w-14 h-14 rounded-full bg-card text-main flex items-center justify-center hover:bg-black hover:text-white transition-colors">
                            <span class="material-symbols-outlined text-[28px]" id="playerPlayPauseIcon">play_arrow</span>
                        </button>
                        <button type="button" onclick="playNextTrack()" class="material-symbols-outlined text-[24px] text-sidebar/70 hover:text-sidebar">skip_next</button>
                        <button type="button" id="btnRepeat" onclick="toggleRepeat()" class="material-symbols-outlined text-[20px] text-sidebar/40 hover:text-sidebar transition-colors">repeat</button>
                    </div>
                    
                    <div class="flex items-center justify-center gap-3 mt-6 w-full px-4">
                        <span class="material-symbols-outlined text-[16px] text-sidebar/50 hover:text-sidebar cursor-pointer" onclick="setVolume(0)">volume_mute</span>
                        <div class="relative w-full h-1.5 bg-black/10 dark:bg-black/20 rounded-full overflow-hidden cursor-pointer" id="playerVolumeTrack" onclick="setVolumeFromClick(event)">
                            <div class="absolute inset-y-0 left-0 bg-accent w-full" id="playerVolumeFill"></div>
                        </div>
                        <span class="material-symbols-outlined text-[16px] text-sidebar/50 hover:text-sidebar cursor-pointer" onclick="setVolume(1)">volume_up</span>
                    </div>
                </div>
            </div>
        </main>
        </div>

        <audio id="library-audio" preload="none"></audio>

        <script>
            // --- Internacionalización (ES / EN / JA) ---
            const I18N = {
                es: {
                    nav_metadata: "Metadatos", nav_download: "Descarga", nav_playlist: "Playlist", nav_library: "Biblioteca",
                    settings_tooltip: "Ajustes", connection_tooltip: "Estado de conexión",
                    settings_title: "Ajustes",
                    settings_theme_title: "TEMA",
                    settings_theme_dark: "Grafito",
                    settings_theme_light: "Aluminio",
                    settings_color_title: "COLOR NANO",
                    settings_language_title: "Idioma",
                    settings_spotify_title: "Cuenta de Spotify",
                    settings_spotify_connected: "Conectado a Spotify",
                    settings_spotify_not_connected: "No conectado a Spotify",
                    settings_spotify_connect_btn: "Conectar con Spotify",
                    settings_spotify_reconnect_btn: "Reconectar con Spotify",
                    settings_credentials_title: "Claves de Acceso",
                    settings_acoustid_label: "Clave de AcoustID",
                    settings_spotify_id_label: "ID de Cliente de Spotify",
                    settings_spotify_secret_label: "Clave Secreta de Spotify",
                    settings_identification_title: "Identificación de Canciones",
                    settings_plan_c_label: "Adivinar por el nombre del archivo cuando no se reconoce la canción",
                    settings_plan_c_hint: "Apagado por defecto: suele ser poco preciso. Si está apagado, esos archivos se reportan como error en vez de adivinar el título/artista.",
                    settings_folders_title: "Carpetas Predeterminadas",
                    settings_library_dir_label: "Carpeta de tu Biblioteca",
                    settings_input_dir_label: "Carpeta de Origen (Metadatos)",
                    settings_output_dir_label: "Carpeta de Destino (Metadatos)",
                    about_tooltip: "Sobre Cicada",
                    about_version: "Versión 1.0.0",
                    about_description: "Herramienta local de organización musical y sincronización automática de metadatos de alta fidelidad.",
                    about_author_label: "Desarrollado por",
                    about_license: "Distribuido bajo Licencia GNU GPLv3",
                    about_github_btn: "Ver en GitHub",
                    common_choose: "Elegir", common_cancel: "Cancelar", common_save: "Guardar",
                    settings_saving: "Guardando...", settings_saved: "Guardado ✓",
                    process_folders_title: "Carpetas de Trabajo",
                    process_source_label: "Carpeta de Origen", process_dest_label: "Carpeta de Destino",
                    process_start_btn: "Iniciar", process_cancel_btn: "Cancelar", process_cancel_full: "Cancelar Proceso",
                    process_recent_activity_title: "Actividad Reciente",
                    process_no_files_yet: "Todavía no se procesó ningún archivo en esta sesión.",
                    process_view_more: "Ver más",
                    process_progress_title: "Progreso", process_connection_title: "Conexión",
                    process_activity_log_title: "Registro de Actividad",
                    process_log_ready: "Listo. Esperando instrucciones...",
                    process_connecting_btn: "Conectando...", process_cancelling_btn: "Cancelando...",
                    process_waiting_first_file: "Esperando el primer archivo...",
                    process_scanning_library: "Escaneando biblioteca",
                    process_starting_status: "Iniciando", process_starting_track: "Iniciando...",
                    process_track_of: "Pista {current} de {total}",
                    process_skipped: "Saltado", process_processing: "Procesando",
                    process_done_all: "Todas las pistas procesadas", process_stopped: "Proceso detenido",
                    process_cancelled_status: "Cancelado", process_completed_status: "Completado",
                    process_report_saved: "Reporte guardado en: ",
                    ws_connected: "Conectado", ws_connecting_short: "Conectando", ws_connecting_dots: "Conectando...",
                    ws_error: "Error", ws_disconnected: "Desconectado",
                    log_ws_error: "Error en la conexión con el servidor (WebSocket desconectado).",
                    log_ws_closed: "Conexión cerrada. Refresca la página para reconectar.",
                    alert_both_paths_required: "Ambas rutas son requeridas.",
                    log_starting_process: "Iniciando petición de procesamiento...",
                    log_connect_error: "Error al conectar con el servidor: ",
                    spotify_link_title: "Enlace de Spotify", spotify_analyze_btn: "Analizar",
                    spotify_tracks_found_title: "Canciones Encontradas", spotify_select_all: "Seleccionar Todas",
                    spotify_hint_paste_link: "Pega un link de Spotify (canción, álbum o playlist) y presiona Analizar para ver las canciones.",
                    spotify_download_selected_btn: "Descargar Seleccionadas",
                    alert_paste_link_first: "Pega un link de Spotify primero.",
                    spotify_analyzing_status: "Analizando enlace...", spotify_analyzing_btn: "Analizando...",
                    error_unknown: "Error desconocido", error_prefix: "Error: ",
                    spotify_could_not_analyze: "No se pudo analizar el enlace.",
                    spotify_no_tracks_found: "No se encontraron pistas en ese enlace.",
                    track_untitled: "Sin título", track_unknown_artist: "Artista Desconocido", track_unknown_album: "Álbum Desconocido",
                    alert_choose_dest_folder: "Elige una carpeta de destino.",
                    alert_select_at_least_one_track: "Selecciona al menos una pista.",
                    spotify_downloading_btn: "Descargando...",
                    log_starting_spotify_download: "Iniciando descarga de {n} pista(s) de Spotify...",
                    spotify_preparing_download: "Preparando descarga",
                    spotify_waiting_first_track: "Esperando la primera pista...",
                    playlists_my_playlists_title: "Mis Playlists", playlists_loading: "Cargando tus playlists...",
                    playlists_choose_hint: "Elige una playlist de la izquierda para ver sus canciones.",
                    playlists_choose_title: "Elige una playlist",
                    playlists_local_library_label: "Tu Biblioteca Local", playlists_replicate_btn: "Replicar Playlist",
                    playlists_preview_title: "Vista Previa de la Playlist",
                    playlists_preview_hint: "Elige una playlist y presiona Replicar Playlist para armar aquí la vista previa. Vas a poder arrastrar las canciones para reordenarlas y destildar las que no quieras incluir.",
                    playlists_m3u8_name_placeholder: "Nombre de la playlist", playlists_generate_btn: "Generar Playlist",
                    playlists_no_playlists_found: "No se encontraron playlists en tu cuenta.",
                    playlists_track_count_suffix: " pistas",
                    playlists_loading_songs: "Cargando canciones...", playlists_no_songs: "Esta playlist no tiene canciones.",
                    alert_choose_local_library_first: "Elige la carpeta de tu biblioteca local primero.",
                    alert_playlist_no_songs_loaded: "Esta playlist no tiene canciones cargadas.",
                    confirm_replicate: "Se van a buscar las {n} canciones de '{name}' en tu biblioteca local ({dir}) para armar una playlist .m3u8.\\n\\n¿Continuar?",
                    playlists_searching_btn: "Buscando...",
                    alert_error_searching_matches: "Error buscando coincidencias: ",
                    playlists_not_found_suffix: " · no encontrada en tu biblioteca",
                    playlists_summary: "{matched}/{total} encontradas · {included} incluidas",
                    alert_error_associating_file: "Error asociando el archivo: ",
                    confirm_manual_match: "Se van a reescribir los tags de:\\n{path}\\n\\ncon los datos de '{artist} - {title}' (Spotify), y el archivo se va a reorganizar dentro de tu biblioteca.\\n\\n¿Continuar?",
                    alert_no_songs_to_generate: "No hay canciones incluidas para generar la playlist.",
                    playlists_generating_btn: "Generando...",
                    alert_playlist_generated: "Playlist generada en: ",
                    log_playlist_generated: "Playlist '{name}' generada en: {path}",
                    alert_error_generating_playlist: "Error generando la playlist: ",
                    default_playlist_name: "Mi Playlist", default_playlist_name_generic: "Playlist",
                    library_my_library_title: "Mi Biblioteca", library_save_scan_btn: "Guardar y Buscar Canciones",
                    library_group_by_label: "Agrupar por", library_group_all: "Todas", library_group_artist: "Artista",
                    library_group_album: "Álbum", library_group_playlist: "Playlist",
                    library_configure_hint: "Configura la carpeta de tu biblioteca arriba para verla aquí.",
                    alert_choose_folder_first: "Elige una carpeta primero.",
                    alert_error_saving_config: "Error guardando la configuración: ",
                    library_scanning: "Escaneando biblioteca...", library_track_count_suffix: " canciones",
                    library_no_songs_in_folder: "No se encontraron canciones en esa carpeta.",
                    library_no_playlist_group: "Sin playlist",
                    alert_error_saving_settings: "Error guardando ajustes: ",
                    player_waiting_status: "En espera", player_cicada_label: "Cicada", player_no_cover: "Sin carátula",
                    player_waiting_title: "En espera...", player_configure_source_hint: "Configura una fuente para comenzar",
                    player_remaining_time_label: "Tiempo Restante", player_progress_label: "Avance",
                    player_cancel_process_btn: "Cancelar Proceso", player_title: "Reproductor",
                    player_nothing_playing: "Nada sonando", player_choose_song_hint: "Elige una canción de tu biblioteca"
                },
                en: {
                    nav_metadata: "Metadata", nav_download: "Download", nav_playlist: "Playlist", nav_library: "Library",
                    settings_tooltip: "Settings", connection_tooltip: "Connection status",
                    settings_title: "Settings",
                    settings_theme_title: "THEME",
                    settings_theme_dark: "Graphite",
                    settings_theme_light: "Aluminum",
                    settings_color_title: "NANO COLOR",
                    settings_language_title: "Language",
                    settings_spotify_title: "Spotify Account",
                    settings_spotify_connected: "Connected to Spotify",
                    settings_spotify_not_connected: "Not connected to Spotify",
                    settings_spotify_connect_btn: "Connect with Spotify",
                    settings_spotify_reconnect_btn: "Reconnect with Spotify",
                    settings_credentials_title: "Access Keys",
                    settings_acoustid_label: "AcoustID Key",
                    settings_spotify_id_label: "Spotify Client ID",
                    settings_spotify_secret_label: "Spotify Client Secret",
                    settings_identification_title: "Song Identification",
                    settings_plan_c_label: "Guess from the file name when a song isn't recognized",
                    settings_plan_c_hint: "Off by default: it tends to be inaccurate. When off, those files are reported as errors instead of guessing the title/artist.",
                    settings_folders_title: "Default Folders",
                    settings_library_dir_label: "Your Library Folder",
                    settings_input_dir_label: "Source Folder (Metadata)",
                    settings_output_dir_label: "Destination Folder (Metadata)",
                    about_tooltip: "About Cicada",
                    about_version: "Version 1.0.0",
                    about_description: "Local music organization tool with high-fidelity automatic metadata syncing.",
                    about_author_label: "Developed by",
                    about_license: "Distributed under the GNU GPLv3 License",
                    about_github_btn: "View on GitHub",
                    common_choose: "Choose", common_cancel: "Cancel", common_save: "Save",
                    settings_saving: "Saving...", settings_saved: "Saved ✓",
                    process_folders_title: "Working Folders",
                    process_source_label: "Source Folder", process_dest_label: "Destination Folder",
                    process_start_btn: "Start", process_cancel_btn: "Cancel", process_cancel_full: "Cancel Process",
                    process_recent_activity_title: "Recent Activity",
                    process_no_files_yet: "No files have been processed in this session yet.",
                    process_view_more: "View more",
                    process_progress_title: "Progress", process_connection_title: "Connection",
                    process_activity_log_title: "Activity Log",
                    process_log_ready: "Ready. Waiting for instructions...",
                    process_connecting_btn: "Connecting...", process_cancelling_btn: "Cancelling...",
                    process_waiting_first_file: "Waiting for the first file...",
                    process_scanning_library: "Scanning library",
                    process_starting_status: "Starting", process_starting_track: "Starting...",
                    process_track_of: "Track {current} of {total}",
                    process_skipped: "Skipped", process_processing: "Processing",
                    process_done_all: "All tracks processed", process_stopped: "Process stopped",
                    process_cancelled_status: "Cancelled", process_completed_status: "Completed",
                    process_report_saved: "Report saved at: ",
                    ws_connected: "Connected", ws_connecting_short: "Connecting", ws_connecting_dots: "Connecting...",
                    ws_error: "Error", ws_disconnected: "Disconnected",
                    log_ws_error: "Error connecting to the server (WebSocket disconnected).",
                    log_ws_closed: "Connection closed. Refresh the page to reconnect.",
                    alert_both_paths_required: "Both paths are required.",
                    log_starting_process: "Starting processing request...",
                    log_connect_error: "Error connecting to the server: ",
                    spotify_link_title: "Spotify Link", spotify_analyze_btn: "Analyze",
                    spotify_tracks_found_title: "Songs Found", spotify_select_all: "Select All",
                    spotify_hint_paste_link: "Paste a Spotify link (song, album or playlist) and press Analyze to see the songs.",
                    spotify_download_selected_btn: "Download Selected",
                    alert_paste_link_first: "Paste a Spotify link first.",
                    spotify_analyzing_status: "Analyzing link...", spotify_analyzing_btn: "Analyzing...",
                    error_unknown: "Unknown error", error_prefix: "Error: ",
                    spotify_could_not_analyze: "Couldn't analyze the link.",
                    spotify_no_tracks_found: "No tracks found in that link.",
                    track_untitled: "Untitled", track_unknown_artist: "Unknown Artist", track_unknown_album: "Unknown Album",
                    alert_choose_dest_folder: "Choose a destination folder.",
                    alert_select_at_least_one_track: "Select at least one track.",
                    spotify_downloading_btn: "Downloading...",
                    log_starting_spotify_download: "Starting download of {n} Spotify track(s)...",
                    spotify_preparing_download: "Preparing download",
                    spotify_waiting_first_track: "Waiting for the first track...",
                    playlists_my_playlists_title: "My Playlists", playlists_loading: "Loading your playlists...",
                    playlists_choose_hint: "Choose a playlist on the left to see its songs.",
                    playlists_choose_title: "Choose a playlist",
                    playlists_local_library_label: "Your Local Library", playlists_replicate_btn: "Replicate Playlist",
                    playlists_preview_title: "Playlist Preview",
                    playlists_preview_hint: "Choose a playlist and press Replicate Playlist to build the preview here. You'll be able to drag songs to reorder them and uncheck the ones you don't want to include.",
                    playlists_m3u8_name_placeholder: "Playlist name", playlists_generate_btn: "Generate Playlist",
                    playlists_no_playlists_found: "No playlists found in your account.",
                    playlists_track_count_suffix: " tracks",
                    playlists_loading_songs: "Loading songs...", playlists_no_songs: "This playlist has no songs.",
                    alert_choose_local_library_first: "Choose your local library folder first.",
                    alert_playlist_no_songs_loaded: "This playlist has no songs loaded.",
                    confirm_replicate: "The {n} songs from '{name}' will be searched for in your local library ({dir}) to build an .m3u8 playlist.\\n\\nContinue?",
                    playlists_searching_btn: "Searching...",
                    alert_error_searching_matches: "Error searching for matches: ",
                    playlists_not_found_suffix: " · not found in your library",
                    playlists_summary: "{matched}/{total} found · {included} included",
                    alert_error_associating_file: "Error associating the file: ",
                    confirm_manual_match: "The tags of:\\n{path}\\n\\nwill be rewritten with the data from '{artist} - {title}' (Spotify), and the file will be reorganized within your library.\\n\\nContinue?",
                    alert_no_songs_to_generate: "There are no songs included to generate the playlist.",
                    playlists_generating_btn: "Generating...",
                    alert_playlist_generated: "Playlist generated at: ",
                    log_playlist_generated: "Playlist '{name}' generated at: {path}",
                    alert_error_generating_playlist: "Error generating the playlist: ",
                    default_playlist_name: "My Playlist", default_playlist_name_generic: "Playlist",
                    library_my_library_title: "My Library", library_save_scan_btn: "Save and Scan Songs",
                    library_group_by_label: "Group by", library_group_all: "All", library_group_artist: "Artist",
                    library_group_album: "Album", library_group_playlist: "Playlist",
                    library_configure_hint: "Set your library folder above to see it here.",
                    alert_choose_folder_first: "Choose a folder first.",
                    alert_error_saving_config: "Error saving the configuration: ",
                    library_scanning: "Scanning library...", library_track_count_suffix: " songs",
                    library_no_songs_in_folder: "No songs found in that folder.",
                    library_no_playlist_group: "No playlist",
                    alert_error_saving_settings: "Error saving settings: ",
                    player_waiting_status: "Waiting", player_cicada_label: "Cicada", player_no_cover: "No cover",
                    player_waiting_title: "Waiting...", player_configure_source_hint: "Set up a source to get started",
                    player_remaining_time_label: "Time Remaining", player_progress_label: "Progress",
                    player_cancel_process_btn: "Cancel Process", player_title: "Player",
                    player_nothing_playing: "Nothing playing", player_choose_song_hint: "Choose a song from your library"
                },
                ja: {
                    nav_metadata: "メタデータ", nav_download: "ダウンロード", nav_playlist: "プレイリスト", nav_library: "ライブラリ",
                    settings_tooltip: "設定", connection_tooltip: "接続状態",
                    settings_title: "設定",
                    settings_theme_title: "テーマ",
                    settings_theme_dark: "グラファイト",
                    settings_theme_light: "アルミニウム",
                    settings_color_title: "ナノカラー",
                    settings_language_title: "言語",
                    settings_spotify_title: "Spotifyアカウント",
                    settings_spotify_connected: "Spotifyに接続済み",
                    settings_spotify_not_connected: "Spotifyに未接続",
                    settings_spotify_connect_btn: "Spotifyで接続",
                    settings_spotify_reconnect_btn: "Spotifyに再接続",
                    settings_credentials_title: "アクセスキー",
                    settings_acoustid_label: "AcoustIDキー",
                    settings_spotify_id_label: "SpotifyクライアントID",
                    settings_spotify_secret_label: "Spotifyクライアントシークレット",
                    settings_identification_title: "楽曲の識別",
                    settings_plan_c_label: "認識できない場合はファイル名から推測する",
                    settings_plan_c_hint: "デフォルトではオフです（精度が低いため）。オフの場合、認識できなかったファイルは推測せずエラーとして報告されます。",
                    settings_folders_title: "デフォルトフォルダ",
                    settings_library_dir_label: "ライブラリフォルダ",
                    settings_input_dir_label: "入力フォルダ（メタデータ）",
                    settings_output_dir_label: "出力フォルダ（メタデータ）",
                    about_tooltip: "Cicadaについて",
                    about_version: "バージョン 1.0.0",
                    about_description: "高精度なメタデータの自動同期を行う、ローカル音楽整理ツール。",
                    about_author_label: "開発者:",
                    about_license: "GNU GPLv3ライセンスの下で配布",
                    about_github_btn: "GitHubで見る",
                    common_choose: "選択", common_cancel: "キャンセル", common_save: "保存",
                    settings_saving: "保存中...", settings_saved: "保存しました ✓",
                    process_folders_title: "作業フォルダ",
                    process_source_label: "入力フォルダ", process_dest_label: "出力フォルダ",
                    process_start_btn: "開始", process_cancel_btn: "キャンセル", process_cancel_full: "処理をキャンセル",
                    process_recent_activity_title: "最近のアクティビティ",
                    process_no_files_yet: "このセッションではまだファイルが処理されていません。",
                    process_view_more: "もっと見る",
                    process_progress_title: "進捗", process_connection_title: "接続",
                    process_activity_log_title: "アクティビティログ",
                    process_log_ready: "準備完了。指示を待機中...",
                    process_connecting_btn: "接続中...", process_cancelling_btn: "キャンセル中...",
                    process_waiting_first_file: "最初のファイルを待機中...",
                    process_scanning_library: "ライブラリをスキャン中",
                    process_starting_status: "開始中", process_starting_track: "開始中...",
                    process_track_of: "{total}中{current}曲目",
                    process_skipped: "スキップ", process_processing: "処理中",
                    process_done_all: "すべての曲を処理しました", process_stopped: "処理を停止しました",
                    process_cancelled_status: "キャンセル済み", process_completed_status: "完了",
                    process_report_saved: "レポートの保存先: ",
                    ws_connected: "接続済み", ws_connecting_short: "接続中", ws_connecting_dots: "接続中...",
                    ws_error: "エラー", ws_disconnected: "切断されました",
                    log_ws_error: "サーバーとの接続エラー（WebSocket切断）。",
                    log_ws_closed: "接続が閉じられました。ページを更新して再接続してください。",
                    alert_both_paths_required: "両方のパスが必要です。",
                    log_starting_process: "処理リクエストを開始しています...",
                    log_connect_error: "サーバーへの接続エラー: ",
                    spotify_link_title: "Spotifyリンク", spotify_analyze_btn: "分析",
                    spotify_tracks_found_title: "見つかった楽曲", spotify_select_all: "すべて選択",
                    spotify_hint_paste_link: "Spotifyのリンク（楽曲、アルバム、またはプレイリスト）を貼り付けて「分析」を押してください。",
                    spotify_download_selected_btn: "選択した曲をダウンロード",
                    alert_paste_link_first: "まずSpotifyのリンクを貼り付けてください。",
                    spotify_analyzing_status: "リンクを分析中...", spotify_analyzing_btn: "分析中...",
                    error_unknown: "不明なエラー", error_prefix: "エラー: ",
                    spotify_could_not_analyze: "リンクを分析できませんでした。",
                    spotify_no_tracks_found: "このリンクには楽曲が見つかりませんでした。",
                    track_untitled: "タイトルなし", track_unknown_artist: "不明のアーティスト", track_unknown_album: "不明のアルバム",
                    alert_choose_dest_folder: "保存先フォルダを選択してください。",
                    alert_select_at_least_one_track: "少なくとも1曲を選択してください。",
                    spotify_downloading_btn: "ダウンロード中...",
                    log_starting_spotify_download: "Spotifyの{n}曲のダウンロードを開始しています...",
                    spotify_preparing_download: "ダウンロードを準備中",
                    spotify_waiting_first_track: "最初の曲を待機中...",
                    playlists_my_playlists_title: "マイプレイリスト", playlists_loading: "プレイリストを読み込み中...",
                    playlists_choose_hint: "左のリストからプレイリストを選んで曲を表示します。",
                    playlists_choose_title: "プレイリストを選択",
                    playlists_local_library_label: "ローカルライブラリ", playlists_replicate_btn: "プレイリストを複製",
                    playlists_preview_title: "プレイリストプレビュー",
                    playlists_preview_hint: "プレイリストを選んで「プレイリストを複製」を押すと、ここにプレビューが作成されます。曲をドラッグして並び替えたり、不要な曲のチェックを外したりできます。",
                    playlists_m3u8_name_placeholder: "プレイリスト名", playlists_generate_btn: "プレイリストを作成",
                    playlists_no_playlists_found: "あなたのアカウントにプレイリストが見つかりませんでした。",
                    playlists_track_count_suffix: " 曲",
                    playlists_loading_songs: "楽曲を読み込み中...", playlists_no_songs: "このプレイリストには楽曲がありません。",
                    alert_choose_local_library_first: "まずローカルライブラリのフォルダを選択してください。",
                    alert_playlist_no_songs_loaded: "このプレイリストには読み込まれた楽曲がありません。",
                    confirm_replicate: "'{name}'の{n}曲をローカルライブラリ（{dir}）から検索して.m3u8プレイリストを作成します。\\n\\n続けますか？",
                    playlists_searching_btn: "検索中...",
                    alert_error_searching_matches: "一致する曲の検索中にエラーが発生しました: ",
                    playlists_not_found_suffix: " ・ ライブラリ内に見つかりません",
                    playlists_summary: "{matched}/{total} 件一致 ・ {included} 件を含む",
                    alert_error_associating_file: "ファイルの関連付け中にエラーが発生しました: ",
                    confirm_manual_match: "次のファイルのタグを書き換えます:\\n{path}\\n\\nSpotifyの'{artist} - {title}'のデータで上書きし、ファイルはライブラリ内で整理されます。\\n\\n続けますか？",
                    alert_no_songs_to_generate: "プレイリストを作成するための曲が含まれていません。",
                    playlists_generating_btn: "作成中...",
                    alert_playlist_generated: "プレイリストを作成しました: ",
                    log_playlist_generated: "プレイリスト「{name}」を作成しました: {path}",
                    alert_error_generating_playlist: "プレイリストの作成中にエラーが発生しました: ",
                    default_playlist_name: "マイプレイリスト", default_playlist_name_generic: "プレイリスト",
                    library_my_library_title: "マイライブラリ", library_save_scan_btn: "保存して曲を検索",
                    library_group_by_label: "グループ化", library_group_all: "すべて", library_group_artist: "アーティスト",
                    library_group_album: "アルバム", library_group_playlist: "プレイリスト",
                    library_configure_hint: "上のライブラリフォルダを設定するとここに表示されます。",
                    alert_choose_folder_first: "まずフォルダを選択してください。",
                    alert_error_saving_config: "設定の保存中にエラーが発生しました: ",
                    library_scanning: "ライブラリをスキャン中...", library_track_count_suffix: " 曲",
                    library_no_songs_in_folder: "このフォルダには楽曲が見つかりませんでした。",
                    library_no_playlist_group: "プレイリストなし",
                    alert_error_saving_settings: "設定の保存中にエラーが発生しました: ",
                    player_waiting_status: "待機中", player_cicada_label: "Cicada", player_no_cover: "カバーなし",
                    player_waiting_title: "待機中...", player_configure_source_hint: "ソースを設定して開始してください",
                    player_remaining_time_label: "残り時間", player_progress_label: "進捗",
                    player_cancel_process_btn: "処理をキャンセル", player_title: "プレーヤー",
                    player_nothing_playing: "再生中の曲はありません", player_choose_song_hint: "ライブラリから曲を選択してください"
                }
            };

            let currentLang = localStorage.getItem("cicada_lang") || "es";

            function t(key, vars) {
                let dict = I18N[currentLang] || I18N.es;
                let str = dict[key] !== undefined ? dict[key] : (I18N.es[key] !== undefined ? I18N.es[key] : key);
                if (vars) {
                    Object.keys(vars).forEach(function(k) {
                        str = str.split("{" + k + "}").join(vars[k]);
                    });
                }
                return str;
            }

            function applyLanguage(lang) {
                currentLang = I18N[lang] ? lang : "es";
                localStorage.setItem("cicada_lang", currentLang);
                document.documentElement.lang = currentLang;

                document.querySelectorAll("[data-i18n]").forEach(function(el) {
                    el.textContent = t(el.getAttribute("data-i18n"));
                });
                document.querySelectorAll("[data-i18n-placeholder]").forEach(function(el) {
                    el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
                });
                document.querySelectorAll("[data-i18n-title]").forEach(function(el) {
                    el.setAttribute("title", t(el.getAttribute("data-i18n-title")));
                });
                document.querySelectorAll(".lang-btn").forEach(function(btn) {
                    btn.classList.toggle("active", btn.dataset.lang === currentLang);
                });

                // Re-renderiza listas dinámicas ya pobladas para que también cambien de idioma
                if (typeof refreshSpotifyDownloadButton === "function") refreshSpotifyDownloadButton();
                if (typeof resolvedSpotifyTracks !== "undefined" && resolvedSpotifyTracks.length > 0) renderSpotifyTrackList();
                if (typeof userPlaylists !== "undefined" && userPlaylists.length > 0) loadSpotifyPlaylists();
                if (typeof replicateMatches !== "undefined" && replicateMatches.length > 0) renderReplicateTrackList();
                if (typeof libraryTracks !== "undefined" && libraryTracks.length > 0) {
                    renderLibraryBrowser();
                    let libCountEl = document.getElementById("library-track-count");
                    if (libCountEl) libCountEl.textContent = libraryTracks.length + t("library_track_count_suffix");
                }
                let settingsModal = document.getElementById("settings-modal");
                if (settingsModal && !settingsModal.classList.contains("hidden") && typeof refreshSpotifyAuthStatus === "function") {
                    refreshSpotifyAuthStatus();
                }

                // Textos de estado que no usan data-i18n porque a veces muestran datos reales
                // (nombre de archivo, título de pista) en vez de una frase traducible.
                if (typeof setWsStatus === "function") setWsStatus(currentWsStatusKey, currentWsColor);
                if (typeof setStatusPill === "function") setStatusPill(currentStatusPillKey, currentStatusPillColor);
                if (!hasStartedProcessing) {
                    let tt = document.getElementById("track-title");
                    let ts = document.getElementById("track-subtitle");
                    if (tt) tt.textContent = t("player_waiting_title");
                    if (ts) ts.textContent = t("player_configure_source_hint");
                }
                if (!hasPlayedTrack) {
                    let ptt = document.getElementById("playerTrackTitle");
                    let pta = document.getElementById("playerTrackArtist");
                    if (ptt) ptt.textContent = t("player_nothing_playing");
                    if (pta) pta.textContent = t("player_choose_song_hint");
                }
            }

            let wsUrl = (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host + "/ws";
            let ws = new WebSocket(wsUrl);

            let logContainer = document.getElementById("log-container");
            let bar = document.getElementById("bar");
            let progressLabel = document.getElementById("progress_label");
            let etaDisplay = document.getElementById("eta_display");
            let statPct = document.getElementById("stat-progress-pct");
            let statCount = document.getElementById("stat-progress-count");
            let statWs = document.getElementById("stat-ws-status");
            let wsStatusLabel = document.getElementById("ws-status-label");
            let wsStatusDot = document.getElementById("ws-status-dot");
            let statusPill = document.getElementById("status-pill");
            let trackTitle = document.getElementById("track-title");
            let trackSubtitle = document.getElementById("track-subtitle");
            let processFileGrid = document.getElementById("process-file-grid");
            let libraryAudio = document.getElementById("library-audio");

            let sessionFiles = [];
            let hasStartedProcessing = false;
            let hasPlayedTrack = false;
            let currentWsStatusKey = "ws_connecting_short";
            let currentWsColor = "#9ca3af";
            let currentStatusPillKey = "player_waiting_status";
            let currentStatusPillColor = "#10b981";

            // --- Navegación entre vistas ---
            function showView(name) {
                document.querySelectorAll(".view").forEach(function(el) { el.classList.remove("active"); });
                document.getElementById("view-" + name).classList.add("active");
                document.querySelectorAll(".nav-item").forEach(function(el) {
                    if (el.dataset.view === name) {
                        el.classList.add("nav-item-active");
                        el.classList.remove("nav-item-inactive");
                    } else {
                        el.classList.remove("nav-item-active");
                        el.classList.add("nav-item-inactive");
                    }
                });
                // El módulo derecho no aporta nada en PLAYLISTS (se oculta); en LIBRARY funciona
                // como reproductor en vez de panel de progreso.
                let processModule = document.getElementById("process-module");
                let progressPanel = document.getElementById("progress-panel");
                let playerPanel = document.getElementById("player-panel");
                if (name === "playlists") {
                    processModule.style.display = "none";
                } else if (name === "library") {
                    processModule.style.display = "flex";
                    progressPanel.classList.add("hidden");
                    progressPanel.classList.remove("flex");
                    playerPanel.classList.remove("hidden");
                    playerPanel.classList.add("flex");
                } else {
                    processModule.style.display = "flex";
                    playerPanel.classList.add("hidden");
                    playerPanel.classList.remove("flex");
                    progressPanel.classList.remove("hidden");
                    progressPanel.classList.add("flex");
                }
            }

            function setWsStatus(key, color) {
                currentWsStatusKey = key;
                currentWsColor = color;
                let label = t(key);
                if (statWs) statWs.textContent = label;
                if (wsStatusLabel) wsStatusLabel.textContent = label;
                if (wsStatusDot) wsStatusDot.style.backgroundColor = color;
            }

            function setStatusPill(key, colorHex) {
                currentStatusPillKey = key;
                currentStatusPillColor = colorHex;
                if (!statusPill) return;
                statusPill.textContent = t(key);
                statusPill.style.color = colorHex;
                statusPill.style.backgroundColor = colorHex + "33";
            }

            function appendLog(message, kind) {
                let colorClass = {
                    "error": "text-[#f43f5e]",
                    "success": "text-secondary",
                    "info": "text-accent",
                    "detail": "text-muted/50 pl-3",
                    "skip": "text-[#f59e0b]"
                }[kind] || "text-muted/70";
                let p = document.createElement("p");
                p.className = "mt-1 " + colorClass;
                p.textContent = "> " + message;
                logContainer.appendChild(p);
                logContainer.scrollTop = logContainer.scrollHeight;
            }

            function fileCardHtml(name, sub) {
                return '<div class="bg-btn border border-theme rounded-lg p-3 flex items-center gap-3">' +
                    '<div class="w-8 h-8 rounded bg-accent/20 flex items-center justify-center flex-shrink-0">' +
                    '<span class="material-symbols-outlined text-accent text-[18px]">audio_file</span></div>' +
                    '<div class="overflow-hidden"><p class="font-data-sm text-[13px] truncate">' + name + '</p>' +
                    '<p class="font-label-caps text-[10px] text-muted/40">' + sub + '</p></div></div>';
            }

            function addFileCard(name, sub) {
                sessionFiles.unshift({name: name, sub: sub});
                if (sessionFiles.length > 24) sessionFiles.pop();
                renderFileGrids();
            }

            function renderFileGrids() {
                if (sessionFiles.length === 0) return;
                let cardsHtml = sessionFiles.map(function(f) { return fileCardHtml(f.name, f.sub); }).join("");
                if (processFileGrid) processFileGrid.innerHTML = cardsHtml;
            }

            async function pickFolder(inputId) {
                try {
                    let res = await fetch('/api/select_folder');
                    let data = await res.json();
                    if (data.path) {
                        document.getElementById(inputId).value = data.path;
                    }
                } catch (e) {
                    console.error("Error al seleccionar carpeta:", e);
                }
            }

            ws.onopen = function() {
                setWsStatus("ws_connected", "#10b981");
            };

            ws.onerror = function() {
                appendLog(t("log_ws_error"), "error");
                setWsStatus("ws_error", "#f43f5e");
                resetUi();
            };

            ws.onclose = function() {
                appendLog(t("log_ws_closed"), "skip");
                setWsStatus("ws_disconnected", "#f43f5e");
                resetUi();
            };

            ws.onmessage = function(event) {
                let data = JSON.parse(event.data);

                if (data.eta) {
                    etaDisplay.textContent = data.eta;
                }

                if (data.type === 'progress') {
                    let pct = Math.round((data.current / data.total) * 100);
                    progressLabel.textContent = pct + "%";
                    bar.style.width = pct + "%";
                    statCount.textContent = data.current + "/" + data.total;
                    statPct.textContent = pct + "%";

                    let isSkipped = data.file.startsWith("(Saltado)");
                    hasStartedProcessing = true;
                    trackTitle.textContent = data.file;
                    trackSubtitle.textContent = t("process_track_of", {current: data.current, total: data.total});
                    setStatusPill(isSkipped ? "process_skipped" : "process_processing", isSkipped ? "#f59e0b" : "#10b981");

                    appendLog("[" + data.current + "/" + data.total + "] " + data.file, isSkipped ? "skip" : "success");
                    addFileCard(data.file, t("process_track_of", {current: data.current, total: data.total}));
                } else if (data.type === 'detail') {
                    appendLog(data.message, "detail");
                } else if (data.type === 'cover') {
                    let img = document.getElementById("currentCover");
                    let placeholder = document.getElementById("coverPlaceholder");
                    if (data.url) {
                        img.src = data.url;
                        img.onload = function() {
                            img.classList.remove("hidden");
                            placeholder.classList.add("hidden");
                        };
                    } else {
                        img.classList.add("hidden");
                        placeholder.classList.remove("hidden");
                    }
                } else if (data.type === 'done') {
                    let isCancel = data.message.includes('cancelado') || data.message.includes('detenido');
                    appendLog(data.message, isCancel ? "skip" : "success");
                    if (data.report_path) {
                        appendLog(t("process_report_saved") + data.report_path, "info");
                    }
                    if (!isCancel) bar.style.width = '100%';

                    progressLabel.textContent = isCancel ? t("process_cancelled_status") : t("process_completed_status");
                    setStatusPill(isCancel ? "process_cancelled_status" : "process_completed_status", isCancel ? "#f43f5e" : "#10b981");
                    hasStartedProcessing = true;
                    trackSubtitle.textContent = isCancel ? t("process_stopped") : t("process_done_all");
                    resetUi();
                } else {
                    let isError = data.type === 'error';
                    appendLog(data.message, isError ? "error" : "info");
                    if (isError && (data.message === "Directorio de entrada no válido." || data.message.includes("cancelado"))) {
                        resetUi();
                    }
                }
            };

            function resetUi() {
                let startBtn = document.getElementById("startBtn");
                if (startBtn) {
                    startBtn.disabled = false;
                    startBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">play_arrow</span> ' + t("process_start_btn");
                    startBtn.classList.remove("opacity-50");
                }
                document.querySelectorAll(".cancel-action").forEach(function(btn) {
                    btn.classList.add("hidden");
                    btn.disabled = false;
                    btn.innerHTML = '<span class="material-symbols-outlined text-[20px]">stop</span> ' + t("process_cancel_btn");
                });
                let downloadBtn = document.getElementById("spotifyDownloadBtn");
                if (downloadBtn) downloadBtn.dataset.busy = "0";
                refreshSpotifyDownloadButton();
            }

            function startProcess() {
                let input_dir = document.getElementById("input_dir").value;
                let output_dir = document.getElementById("output_dir").value;

                if (!input_dir || !output_dir) {
                    alert(t("alert_both_paths_required"));
                    return;
                }

                let startBtn = document.getElementById("startBtn");
                startBtn.disabled = true;
                startBtn.innerHTML = '<span class="material-symbols-outlined text-[20px]">sync</span> ' + t("process_connecting_btn");
                startBtn.classList.add("opacity-50");
                document.querySelectorAll(".cancel-action").forEach(function(btn) { btn.classList.remove("hidden"); });

                logContainer.innerHTML = "";
                appendLog(t("log_starting_process"), "info");
                bar.style.width = '0%';
                progressLabel.textContent = "0%";
                statCount.textContent = "0/0";
                statPct.textContent = "0%";
                setStatusPill("process_starting_status", "#06b6d4");
                hasStartedProcessing = true;
                trackTitle.textContent = t("process_starting_track");
                trackSubtitle.textContent = t("process_scanning_library");
                sessionFiles = [];
                if (processFileGrid) processFileGrid.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("process_waiting_first_file") + '</p>';

                let img = document.getElementById("currentCover");
                let placeholder = document.getElementById("coverPlaceholder");
                img.classList.add("hidden");
                placeholder.classList.remove("hidden");

                fetch('/api/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({input_dir: input_dir, output_dir: output_dir})
                }).then(function(r) { return r.json(); }).then(function(d) {
                    console.log(d);
                }).catch(function(e) {
                    appendLog(t("log_connect_error") + e, "error");
                    resetUi();
                });
            }

            function cancelProcess() {
                document.querySelectorAll(".cancel-action").forEach(function(btn) {
                    btn.disabled = true;
                    btn.innerHTML = '<span class="material-symbols-outlined text-[20px]">sync</span> ' + t("process_cancelling_btn");
                });

                fetch('/api/cancel', {method: 'POST'})
                    .then(function(r) { return r.json(); })
                    .then(function(d) { console.log(d); })
                    .catch(function(e) { console.error("Error al cancelar:", e); });
            }

            // --- Pestaña SPOTIFY: resolver enlace, previsualizar y seleccionar pistas ---
            let resolvedSpotifyTracks = [];

            function escapeHtml(text) {
                let div = document.createElement("div");
                div.textContent = text == null ? "" : text;
                return div.innerHTML;
            }

            async function resolveSpotifyUrl() {
                let url = document.getElementById("spotify_url").value.trim();
                let statusEl = document.getElementById("spotify-resolve-status");
                let listEl = document.getElementById("spotify-track-list");
                let resolveBtn = document.getElementById("resolveBtn");

                if (!url) {
                    alert(t("alert_paste_link_first"));
                    return;
                }

                resolveBtn.disabled = true;
                resolveBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">sync</span> ' + t("spotify_analyzing_btn");
                statusEl.textContent = "";
                listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("spotify_analyzing_status") + '</p>';

                try {
                    let res = await fetch('/api/spotify/resolve', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({url: url})
                    });
                    let data = await res.json();

                    if (!res.ok) {
                        throw new Error(data.detail || t("error_unknown"));
                    }

                    resolvedSpotifyTracks = data.tracks || [];
                    renderSpotifyTrackList();
                } catch (e) {
                    statusEl.textContent = t("error_prefix") + e.message;
                    listEl.innerHTML = '<p class="font-data-sm text-[13px] text-[#f43f5e]">' + t("spotify_could_not_analyze") + '</p>';
                    resolvedSpotifyTracks = [];
                    updateSpotifySelectionCount();
                } finally {
                    resolveBtn.disabled = false;
                    resolveBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">search</span> ' + t("spotify_analyze_btn");
                }
            }

            function renderSpotifyTrackList() {
                let listEl = document.getElementById("spotify-track-list");
                let countEl = document.getElementById("spotify-track-count");

                if (resolvedSpotifyTracks.length === 0) {
                    listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("spotify_no_tracks_found") + '</p>';
                    countEl.textContent = "";
                    updateSpotifySelectionCount();
                    return;
                }

                countEl.textContent = "(" + resolvedSpotifyTracks.length + ")";

                listEl.innerHTML = resolvedSpotifyTracks.map(function(track, i) {
                    let cover = track.artwork_url
                        ? '<img src="' + track.artwork_url + '" class="w-10 h-10 rounded object-cover bg-input flex-shrink-0"/>'
                        : '<div class="w-10 h-10 rounded bg-input flex items-center justify-center flex-shrink-0"><span class="material-symbols-outlined text-[18px] text-muted/40">music_note</span></div>';
                    let title = escapeHtml(track.title || t("track_untitled"));
                    let artist = escapeHtml(track.artist || t("track_unknown_artist"));
                    return '<label class="flex items-center gap-3 bg-btn border border-theme rounded-lg p-3 cursor-pointer hover:bg-btn-hover transition-colors">' +
                        '<input type="checkbox" class="spotify-track-checkbox cicada-checkbox" data-index="' + i + '" checked onchange="updateSpotifySelectionCount()"/>' +
                        cover +
                        '<div class="overflow-hidden flex-1">' +
                        '<p class="font-data-sm text-[14px] truncate">' + title + '</p>' +
                        '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + artist + '</p>' +
                        '</div></label>';
                }).join("");

                let selectAll = document.getElementById("spotify-select-all");
                selectAll.checked = true;
                selectAll.indeterminate = false;
                updateSpotifySelectionCount();
            }

            function toggleSelectAllTracks(checked) {
                document.querySelectorAll(".spotify-track-checkbox").forEach(function(cb) { cb.checked = checked; });
                updateSpotifySelectionCount();
            }

            function updateSpotifySelectionCount() {
                let checkboxes = document.querySelectorAll(".spotify-track-checkbox");
                let selected = document.querySelectorAll(".spotify-track-checkbox:checked").length;

                let selectAll = document.getElementById("spotify-select-all");
                if (selectAll) {
                    selectAll.checked = checkboxes.length > 0 && selected === checkboxes.length;
                    selectAll.indeterminate = selected > 0 && selected < checkboxes.length;
                }

                refreshSpotifyDownloadButton();
            }

            function refreshSpotifyDownloadButton() {
                let btn = document.getElementById("spotifyDownloadBtn");
                if (!btn) return;
                if (btn.disabled && btn.dataset.busy === "1") return;
                let n = document.querySelectorAll(".spotify-track-checkbox:checked").length;
                btn.disabled = n === 0;
                btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">download</span> ' + t("spotify_download_selected_btn") + ' (<span id="spotify-selected-count">' + n + '</span>)';
            }

            function startSpotifyDownload() {
                let output_dir = document.getElementById("spotify_output_dir").value;
                if (!output_dir) {
                    alert(t("alert_choose_dest_folder"));
                    return;
                }

                let selectedTracks = Array.from(document.querySelectorAll(".spotify-track-checkbox"))
                    .filter(function(cb) { return cb.checked; })
                    .map(function(cb) { return resolvedSpotifyTracks[parseInt(cb.dataset.index, 10)]; });

                if (selectedTracks.length === 0) {
                    alert(t("alert_select_at_least_one_track"));
                    return;
                }

                let downloadBtn = document.getElementById("spotifyDownloadBtn");
                downloadBtn.disabled = true;
                downloadBtn.dataset.busy = "1";
                downloadBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">sync</span> ' + t("spotify_downloading_btn");
                document.querySelectorAll(".cancel-action").forEach(function(btn) { btn.classList.remove("hidden"); });

                logContainer.innerHTML = "";
                appendLog(t("log_starting_spotify_download", {n: selectedTracks.length}), "info");
                bar.style.width = '0%';
                progressLabel.textContent = "0%";
                statCount.textContent = "0/0";
                statPct.textContent = "0%";
                setStatusPill("process_starting_status", "#06b6d4");
                hasStartedProcessing = true;
                trackTitle.textContent = t("process_starting_track");
                trackSubtitle.textContent = t("spotify_preparing_download");
                sessionFiles = [];
                if (processFileGrid) processFileGrid.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("spotify_waiting_first_track") + '</p>';

                let img = document.getElementById("currentCover");
                let placeholder = document.getElementById("coverPlaceholder");
                img.classList.add("hidden");
                placeholder.classList.remove("hidden");

                fetch('/api/spotify/download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({tracks: selectedTracks, output_dir: output_dir})
                }).then(function(r) { return r.json(); }).then(function(d) {
                    console.log(d);
                }).catch(function(e) {
                    appendLog(t("log_connect_error") + e, "error");
                    resetUi();
                });
            }

            // --- Pestaña PLAYLISTS: navegar playlists, ver canciones y replicarlas contra la biblioteca local ---
            let userPlaylists = [];
            let currentPlaylistTracks = [];
            let currentPlaylistName = "";
            let replicateMatches = [];

            async function loadSpotifyPlaylists() {
                let listEl = document.getElementById("playlists-list");
                listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("playlists_loading") + '</p>';
                try {
                    let res = await fetch('/api/spotify/playlists');
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    userPlaylists = data.playlists || [];
                    if (userPlaylists.length === 0) {
                        listEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("playlists_no_playlists_found") + '</p>';
                        return;
                    }

                    listEl.innerHTML = userPlaylists.map(function(p, i) {
                        let cover = p.image_url
                            ? '<img src="' + p.image_url + '" class="w-10 h-10 rounded object-cover bg-input flex-shrink-0"/>'
                            : '<div class="w-10 h-10 rounded bg-input flex items-center justify-center flex-shrink-0"><span class="material-symbols-outlined text-[18px] text-muted/40">queue_music</span></div>';
                        return '<div class="playlist-item flex items-center gap-3 bg-btn border border-theme rounded-lg p-2 cursor-pointer hover:bg-btn-hover transition-colors" data-index="' + i + '" onclick="selectPlaylist(' + i + ')">' +
                            cover +
                            '<div class="overflow-hidden flex-1">' +
                            '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(p.name) + '</p>' +
                            '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + p.track_count + t("playlists_track_count_suffix") + '</p>' +
                            '</div></div>';
                    }).join("");
                } catch (e) {
                    listEl.innerHTML = '<p class="font-data-sm text-[13px] text-[#f43f5e]">' + t("error_prefix") + e.message + '</p>';
                }
            }

            async function selectPlaylist(index) {
                let playlist = userPlaylists[index];
                if (!playlist) return;

                document.querySelectorAll(".playlist-item").forEach(function(el) { el.classList.remove("ring-2", "ring-primary"); });
                let el = document.querySelector('.playlist-item[data-index="' + index + '"]');
                if (el) el.classList.add("ring-2", "ring-primary");

                currentPlaylistName = playlist.name;
                let titleEl = document.getElementById("playlist-detail-title");
                titleEl.removeAttribute("data-i18n");
                titleEl.textContent = playlist.name;

                let trackListEl = document.getElementById("playlist-track-list");
                trackListEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("playlists_loading_songs") + '</p>';
                document.getElementById("replicate-controls").style.display = "none";

                // Al cambiar de playlist, el preview de replicación anterior ya no aplica
                replicateMatches = [];
                document.getElementById("replicate-track-list").innerHTML = "";
                document.getElementById("replicate-match-summary").textContent = "";
                document.getElementById("generate-m3u8-controls").classList.add("hidden");
                document.getElementById("generate-m3u8-controls").classList.remove("flex");
                document.getElementById("replicate-empty-hint").classList.remove("hidden");

                try {
                    let res = await fetch('/api/spotify/resolve', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({url: 'https://open.spotify.com/playlist/' + playlist.id})
                    });
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    currentPlaylistTracks = data.tracks || [];
                    renderPlaylistTrackPreview();
                    document.getElementById("replicate-controls").style.display = "flex";
                } catch (e) {
                    trackListEl.innerHTML = '<p class="font-data-sm text-[13px] text-[#f43f5e]">' + t("error_prefix") + e.message + '</p>';
                }
            }

            function renderPlaylistTrackPreview() {
                let trackListEl = document.getElementById("playlist-track-list");
                if (currentPlaylistTracks.length === 0) {
                    trackListEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("playlists_no_songs") + '</p>';
                    return;
                }
                trackListEl.innerHTML = currentPlaylistTracks.map(function(track) {
                    return '<div class="flex items-center gap-3 bg-btn border border-theme rounded-lg p-2">' +
                        '<span class="material-symbols-outlined text-[16px] text-muted/40">music_note</span>' +
                        '<div class="overflow-hidden flex-1">' +
                        '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(track.title) + '</p>' +
                        '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + escapeHtml(track.artist) + '</p>' +
                        '</div></div>';
                }).join("");
            }

            async function replicatePlaylist() {
                let libraryDir = document.getElementById("library_dir").value.trim();
                if (!libraryDir) {
                    alert(t("alert_choose_local_library_first"));
                    return;
                }
                if (currentPlaylistTracks.length === 0) {
                    alert(t("alert_playlist_no_songs_loaded"));
                    return;
                }

                let confirmed = confirm(t("confirm_replicate", {n: currentPlaylistTracks.length, name: currentPlaylistName, dir: libraryDir}));
                if (!confirmed) return;

                let btn = document.getElementById("replicateBtn");
                btn.disabled = true;
                btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">sync</span> ' + t("playlists_searching_btn");

                try {
                    let res = await fetch('/api/library/match', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({tracks: currentPlaylistTracks, library_dir: libraryDir})
                    });
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    // Conservamos el track de Spotify completo (álbum, artwork, ISRC, etc.), no
                    // solo title/artist/path: hace falta para re-etiquetar si el usuario asocia
                    // manualmente un archivo que el fuzzy matching no encontró solo.
                    replicateMatches = data.matches.map(function(m) {
                        let entry = Object.assign({}, m);
                        entry.included = !!m.path;
                        return entry;
                    });

                    document.getElementById("replicate-empty-hint").classList.add("hidden");
                    document.getElementById("generate-m3u8-controls").classList.remove("hidden");
                    document.getElementById("generate-m3u8-controls").classList.add("flex");
                    document.getElementById("m3u8_name").value = currentPlaylistName || t("default_playlist_name");
                    renderReplicateTrackList();
                } catch (e) {
                    alert(t("alert_error_searching_matches") + e.message);
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">content_copy</span> ' + t("playlists_replicate_btn");
                }
            }

            function renderReplicateTrackList() {
                let container = document.getElementById("replicate-track-list");
                container.innerHTML = replicateMatches.map(function(m, i) {
                    let matched = !!m.path;
                    let rowClasses = matched ? "bg-btn" : "bg-white/[0.02] opacity-75";
                    let statusIcon = matched
                        ? '<span class="material-symbols-outlined text-[16px] text-secondary" title="Encontrada">check_circle</span>'
                        : '<span class="material-symbols-outlined text-[16px] text-muted/40" title="No encontrada">help</span>';
                    // Solo las pistas no encontradas automáticamente pueden asociarse a mano;
                    // las que ya matchearon quedan intactas.
                    let manualBtn = matched ? '' :
                        '<button type="button" onclick="manualMatchTrack(' + i + ')" title="Asociar con un archivo de mi biblioteca" class="material-symbols-outlined text-[16px] text-accent/80 hover:text-accent">attach_file</button>';
                    return '<div class="replicate-track-row flex items-center gap-2 ' + rowClasses + ' border border-transparent rounded-lg p-2" ' +
                        'draggable="true" data-index="' + i + '" ' +
                        'ondragstart="handleTrackDragStart(event, ' + i + ')" ondragend="handleTrackDragEnd(event)" ' +
                        'ondragover="handleTrackDragOver(event)" ondragleave="handleTrackDragLeave(event)" ondrop="handleTrackDrop(event, ' + i + ')">' +
                        '<span class="material-symbols-outlined text-[18px] text-muted/40 cursor-grab" title="Arrastrar para reordenar">drag_indicator</span>' +
                        '<input type="checkbox" class="cicada-checkbox" data-index="' + i + '" ' + (matched && m.included ? 'checked' : '') + ' ' + (matched ? '' : 'disabled') + ' onchange="toggleReplicateTrackIncluded(' + i + ', this.checked)"/>' +
                        statusIcon +
                        '<div class="overflow-hidden flex-1">' +
                        '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(m.title) + '</p>' +
                        '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + escapeHtml(m.artist) + (matched ? '' : t("playlists_not_found_suffix")) + '</p>' +
                        '</div>' + manualBtn + '</div>';
                }).join("");
                updateReplicateSummary();
            }

            // --- Drag and drop libre para reordenar el preview de la playlist ---
            let dragSourceIndex = null;

            function handleTrackDragStart(e, index) {
                dragSourceIndex = index;
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData("text/plain", String(index));
                e.currentTarget.classList.add("opacity-40");
            }

            function handleTrackDragEnd(e) {
                e.currentTarget.classList.remove("opacity-40");
                document.querySelectorAll(".replicate-track-row").forEach(function(row) {
                    row.classList.remove("border-accent");
                });
                dragSourceIndex = null;
            }

            function handleTrackDragOver(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                e.currentTarget.classList.add("border-accent");
            }

            function handleTrackDragLeave(e) {
                e.currentTarget.classList.remove("border-accent");
            }

            function handleTrackDrop(e, targetIndex) {
                e.preventDefault();
                e.currentTarget.classList.remove("border-accent");
                if (dragSourceIndex === null || dragSourceIndex === targetIndex) return;
                let moved = replicateMatches.splice(dragSourceIndex, 1)[0];
                replicateMatches.splice(targetIndex, 0, moved);
                dragSourceIndex = null;
                renderReplicateTrackList();
            }

            function toggleReplicateTrackIncluded(index, checked) {
                if (replicateMatches[index]) replicateMatches[index].included = checked;
                updateReplicateSummary();
            }

            function updateReplicateSummary() {
                let matchedCount = replicateMatches.filter(function(m) { return !!m.path; }).length;
                let includedCount = replicateMatches.filter(function(m) { return m.included && m.path; }).length;
                document.getElementById("replicate-match-summary").textContent = t("playlists_summary", {matched: matchedCount, total: replicateMatches.length, included: includedCount});
                document.getElementById("generateM3u8Btn").disabled = includedCount === 0;
            }
            
            async function manualMatchTrack(index) {
                let entry = replicateMatches[index];
                if (!entry) return;

                let libraryDir = document.getElementById("library_dir").value.trim();
                if (!libraryDir) {
                    alert(t("alert_choose_local_library_first"));
                    return;
                }

                let pickRes = await fetch('/api/select_file');
                let pickData = await pickRes.json();
                if (!pickData.path) return; // el usuario cerró el diálogo sin elegir nada

                let confirmed = confirm(t("confirm_manual_match", {path: pickData.path, artist: entry.artist, title: entry.title}));
                if (!confirmed) return;

                try {
                    let res = await fetch('/api/library/manual_match', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({track: entry, file_path: pickData.path, library_dir: libraryDir})
                    });
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    replicateMatches[index].path = data.path;
                    replicateMatches[index].included = true;
                    renderReplicateTrackList();
                } catch (e) {
                    alert(t("alert_error_associating_file") + e.message);
                }
            }

            async function generatePlaylistM3u8() {
                let name = document.getElementById("m3u8_name").value.trim() || t("default_playlist_name_generic");
                let libraryDir = document.getElementById("library_dir").value.trim();
                let filePaths = replicateMatches.filter(function(m) { return m.included && m.path; }).map(function(m) { return m.path; });

                if (filePaths.length === 0) {
                    alert(t("alert_no_songs_to_generate"));
                    return;
                }

                let btn = document.getElementById("generateM3u8Btn");
                btn.disabled = true;
                btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">sync</span> ' + t("playlists_generating_btn");

                try {
                    let res = await fetch('/api/library/generate_playlist', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({playlist_name: name, file_paths: filePaths, output_dir: libraryDir})
                    });
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    alert(t("alert_playlist_generated") + data.m3u8_path);
                    appendLog(t("log_playlist_generated", {name: name, path: data.m3u8_path}), "success");
                } catch (e) {
                    alert(t("alert_error_generating_playlist") + e.message);
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">save</span> ' + t("playlists_generate_btn");
                }
            }

            // --- Pestaña LIBRARY: carpeta persistente, navegador agrupable y reproductor ---
            let libraryTracks = [];
            let libraryPlaylists = [];
            let libraryGrouping = "all";
            let libraryQueues = {};
            let currentQueueKey = null;
            let currentQueueIndex = -1;

            async function loadLibraryConfig() {
                try {
                    let res = await fetch('/api/library/config');
                    let data = await res.json();
                    let dir = data.library_dir || "";
                    if (!dir) return;

                    let browseInput = document.getElementById("library_browse_dir");
                    if (browseInput) browseInput.value = dir;
                    // Precarga también el campo de la pestaña PLAYLISTS si todavía está vacío
                    let replicateInput = document.getElementById("library_dir");
                    if (replicateInput && !replicateInput.value) replicateInput.value = dir;

                    await scanLibrary(dir);
                } catch (e) {
                    console.error("Error cargando configuración de biblioteca:", e);
                }
            }

            async function saveLibraryDirAndScan() {
                let dir = document.getElementById("library_browse_dir").value.trim();
                if (!dir) {
                    alert(t("alert_choose_folder_first"));
                    return;
                }
                try {
                    await fetch('/api/library/config', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({library_dir: dir})
                    });
                    let replicateInput = document.getElementById("library_dir");
                    if (replicateInput) replicateInput.value = dir;
                    await scanLibrary(dir);
                } catch (e) {
                    alert(t("alert_error_saving_config") + e.message);
                }
            }

            async function scanLibrary(dir) {
                let browserEl = document.getElementById("library-browser");
                browserEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("library_scanning") + '</p>';
                try {
                    let res = await fetch('/api/library/browse?library_dir=' + encodeURIComponent(dir));
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    libraryTracks = data.tracks || [];
                    libraryPlaylists = data.playlists || [];
                    document.getElementById("library-track-count").textContent = libraryTracks.length + t("library_track_count_suffix");
                    renderLibraryBrowser();
                } catch (e) {
                    browserEl.innerHTML = '<p class="font-data-sm text-[13px] text-[#f43f5e]">' + t("error_prefix") + e.message + '</p>';
                }
            }

            function setLibraryGrouping(group) {
                libraryGrouping = group;
                document.querySelectorAll(".library-group-btn").forEach(function(btn) {
                    btn.classList.toggle("active", btn.dataset.group === group);
                });
                renderLibraryBrowser();
            }

            function libraryTrackRowHtml(track, queueKey, index) {
                let subtitle = libraryGrouping === "album"
                    ? escapeHtml(track.artist || "")
                    : escapeHtml(track.artist || "") + (track.album ? " &middot; " + escapeHtml(track.album) : "");
                return '<div class="flex items-center gap-3 px-2 py-1.5 rounded-lg cursor-pointer hover:bg-btn-hover transition-colors" onclick="playFromQueue(\\'' + queueKey + '\\', ' + index + ')">' +
                    '<span class="material-symbols-outlined text-[18px] text-muted/40">music_note</span>' +
                    '<div class="overflow-hidden flex-1">' +
                    '<p class="font-data-sm text-[14px] truncate">' + escapeHtml(track.title) + '</p>' +
                    '<p class="font-label-caps text-[11px] text-muted/40 truncate">' + subtitle + '</p>' +
                    '</div></div>';
            }

            function libraryGroupSectionHtml(name, tracks, key) {
                return '<details class="library-group" open>' +
                    '<summary class="font-label-caps text-[13px] text-main font-bold py-2 mt-1">' + escapeHtml(name) +
                    ' <span class="font-normal text-[12px] text-muted">(' + tracks.length + ')</span></summary>' +
                    '<div class="flex flex-col gap-0.5 pl-3 pb-2">' +
                    tracks.map(function(track, i) { return libraryTrackRowHtml(track, key, i); }).join("") +
                    '</div></details>';
            }

            function renderLibraryBrowser() {
                let browserEl = document.getElementById("library-browser");
                libraryQueues = {};

                if (libraryTracks.length === 0) {
                    browserEl.innerHTML = '<p class="font-data-sm text-[13px] text-muted/40">' + t("library_no_songs_in_folder") + '</p>';
                    return;
                }

                if (libraryGrouping === "all") {
                    let sorted = libraryTracks.slice().sort(function(a, b) {
                        return ((a.artist || "") + (a.album || "") + (a.title || "")).localeCompare((b.artist || "") + (b.album || "") + (b.title || ""));
                    });
                    libraryQueues["all"] = sorted;
                    browserEl.innerHTML = sorted.map(function(track, i) { return libraryTrackRowHtml(track, "all", i); }).join("");
                    return;
                }

                if (libraryGrouping === "playlist") {
                    let sections = libraryPlaylists.map(function(p) {
                        let pathSet = new Set(p.paths);
                        return {name: p.name, tracks: libraryTracks.filter(function(track) { return pathSet.has(track.path); })};
                    });
                    let assigned = new Set();
                    sections.forEach(function(s) { s.tracks.forEach(function(track) { assigned.add(track.path); }); });
                    let unassigned = libraryTracks.filter(function(track) { return !assigned.has(track.path); });
                    if (unassigned.length > 0) sections.push({name: t("library_no_playlist_group"), tracks: unassigned});

                    browserEl.innerHTML = sections.filter(function(s) { return s.tracks.length > 0; }).map(function(s) {
                        let key = "pl:" + s.name;
                        libraryQueues[key] = s.tracks;
                        return libraryGroupSectionHtml(s.name, s.tracks, key);
                    }).join("");
                    return;
                }

                let groupKeyFn = libraryGrouping === "album"
                    ? function(track) { return (track.artist || t("track_unknown_artist")) + " — " + (track.album || t("track_unknown_album")); }
                    : function(track) { return track.artist || t("track_unknown_artist"); };

                let groups = {};
                libraryTracks.forEach(function(track) {
                    let key = groupKeyFn(track);
                    if (!groups[key]) groups[key] = [];
                    groups[key].push(track);
                });
                let groupNames = Object.keys(groups).sort(function(a, b) { return a.localeCompare(b); });
                browserEl.innerHTML = groupNames.map(function(name) {
                    let key = libraryGrouping + ":" + name;
                    libraryQueues[key] = groups[name];
                    return libraryGroupSectionHtml(name, groups[name], key);
                }).join("");
            }

            // --- Reproductor ---
            function playFromQueue(key, index) {
                currentQueueKey = key;
                currentQueueIndex = index;
                playCurrentQueueTrack();
            }

            function playCurrentQueueTrack() {
                let queue = libraryQueues[currentQueueKey];
                if (!queue || !queue[currentQueueIndex]) return;
                let track = queue[currentQueueIndex];

                hasPlayedTrack = true;
                document.getElementById("playerTrackTitle").textContent = track.title || t("track_untitled");
                document.getElementById("playerTrackArtist").textContent = (track.artist || "") + (track.album ? " · " + track.album : "");

                let cover = document.getElementById("playerCover");
                let placeholder = document.getElementById("playerCoverPlaceholder");
                cover.classList.add("hidden");
                placeholder.classList.remove("hidden");
                cover.onload = function() { cover.classList.remove("hidden"); placeholder.classList.add("hidden"); };
                cover.onerror = function() { cover.classList.add("hidden"); placeholder.classList.remove("hidden"); };
                cover.src = '/api/library/artwork?path=' + encodeURIComponent(track.path);

                libraryAudio.src = '/api/library/stream?path=' + encodeURIComponent(track.path);
                libraryAudio.play().catch(function(e) { console.error("Error reproduciendo:", e); });
                setPlayPauseIcon(true);
            }

            function togglePlayPause() {
                if (!libraryAudio.src) return;
                if (libraryAudio.paused) {
                    libraryAudio.play();
                    setPlayPauseIcon(true);
                } else {
                    libraryAudio.pause();
                    setPlayPauseIcon(false);
                }
            }

            function setPlayPauseIcon(playing) {
                document.getElementById("playerPlayPauseIcon").textContent = playing ? "pause" : "play_arrow";
            }

            let isShuffle = false;
            let repeatMode = 0;

            function toggleShuffle() {
                isShuffle = !isShuffle;
                let btn = document.getElementById("btnShuffle");
                if (isShuffle) {
                    btn.classList.remove("text-sidebar/40");
                    btn.classList.add("text-accent");
                } else {
                    btn.classList.remove("text-accent");
                    btn.classList.add("text-sidebar/40");
                }
            }

            function toggleRepeat() {
                repeatMode = (repeatMode + 1) % 3;
                let btn = document.getElementById("btnRepeat");
                if (repeatMode === 0) {
                    btn.classList.remove("text-accent");
                    btn.classList.add("text-sidebar/40");
                    btn.textContent = "repeat";
                } else if (repeatMode === 1) {
                    btn.classList.remove("text-sidebar/40");
                    btn.classList.add("text-accent");
                    btn.textContent = "repeat";
                } else if (repeatMode === 2) {
                    btn.classList.remove("text-sidebar/40");
                    btn.classList.add("text-accent");
                    btn.textContent = "repeat_one";
                }
            }

            function playNextTrack(auto = false) {
                let queue = libraryQueues[currentQueueKey];
                if (!queue) return;
                
                if (auto === true && repeatMode === 2) {
                    libraryAudio.currentTime = 0;
                    libraryAudio.play();
                    return;
                }
                
                if (isShuffle) {
                    currentQueueIndex = Math.floor(Math.random() * queue.length);
                } else {
                    if (currentQueueIndex >= queue.length - 1) {
                        if (repeatMode === 1) {
                            currentQueueIndex = 0;
                        } else {
                            if (auto === true) setPlayPauseIcon(false);
                            return;
                        }
                    } else {
                        currentQueueIndex += 1;
                    }
                }
                playCurrentQueueTrack();
            }

            function playPrevTrack() {
                let queue = libraryQueues[currentQueueKey];
                if (!queue) return;
                
                if (isShuffle) {
                    currentQueueIndex = Math.floor(Math.random() * queue.length);
                } else {
                    if (currentQueueIndex <= 0) {
                        currentQueueIndex = 0;
                    } else {
                        currentQueueIndex -= 1;
                    }
                }
                playCurrentQueueTrack();
            }

            function formatTime(seconds) {
                if (!isFinite(seconds) || seconds < 0) return "0:00";
                let m = Math.floor(seconds / 60);
                let s = Math.floor(seconds % 60);
                return m + ":" + (s < 10 ? "0" : "") + s;
            }

            function seekPlayer(e) {
                if (!libraryAudio.duration) return;
                let rect = document.getElementById("playerSeekTrack").getBoundingClientRect();
                let ratio = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1);
                libraryAudio.currentTime = ratio * libraryAudio.duration;
            }

            function setVolumeFromClick(e) {
                let rect = document.getElementById("playerVolumeTrack").getBoundingClientRect();
                let ratio = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1);
                setVolume(ratio);
            }

            function setVolume(vol) {
                libraryAudio.volume = vol;
            }

            libraryAudio.addEventListener("volumechange", function() {
                let pct = libraryAudio.volume * 100;
                document.getElementById("playerVolumeFill").style.width = pct + "%";
            });

            libraryAudio.addEventListener("timeupdate", function() {
                if (!libraryAudio.duration) return;
                let pct = (libraryAudio.currentTime / libraryAudio.duration) * 100;
                document.getElementById("playerSeekFill").style.width = pct + "%";
                document.getElementById("playerCurrentTime").textContent = formatTime(libraryAudio.currentTime);
                document.getElementById("playerDuration").textContent = formatTime(libraryAudio.duration);
            });
            libraryAudio.addEventListener("ended", function() {
                playNextTrack(true);
            });
            libraryAudio.addEventListener("pause", function() { setPlayPauseIcon(false); });
            libraryAudio.addEventListener("play", function() { setPlayPauseIcon(true); });

            // --- Ajustes (modal): credenciales de API, toggle del Plan C, carpetas predeterminadas ---
            function openSettings() {
                loadSettingsIntoForm();
                refreshSpotifyAuthStatus();
                let modal = document.getElementById("settings-modal");
                modal.classList.remove("hidden");
                modal.classList.add("flex");
            }

            async function refreshSpotifyAuthStatus() {
                let statusEl = document.getElementById("settings-spotify-status");
                let btn = document.getElementById("settings-spotify-connect-btn");
                if (!statusEl || !btn) return;
                try {
                    let res = await fetch('/api/auth/status');
                    let data = await res.json();
                    if (data.connected) {
                        statusEl.textContent = t("settings_spotify_connected");
                        btn.textContent = t("settings_spotify_reconnect_btn");
                    } else {
                        statusEl.textContent = t("settings_spotify_not_connected");
                        btn.textContent = t("settings_spotify_connect_btn");
                    }
                } catch (e) {
                    console.error("Error consultando el estado de Spotify:", e);
                }
            }

            function closeSettings() {
                let modal = document.getElementById("settings-modal");
                modal.classList.add("hidden");
                modal.classList.remove("flex");
            }

            // --- Modal "Sobre" (About): se abre al hacer clic en el logo "C." de la barra lateral ---
            function openAbout() {
                let modal = document.getElementById("about-modal");
                modal.classList.remove("hidden");
                modal.classList.add("flex");
            }

            function closeAbout() {
                let modal = document.getElementById("about-modal");
                modal.classList.add("hidden");
                modal.classList.remove("flex");
            }

            function toggleSecretVisibility(inputId, btn) {
                let input = document.getElementById(inputId);
                if (input.type === "password") {
                    input.type = "text";
                    btn.textContent = "visibility_off";
                } else {
                    input.type = "password";
                    btn.textContent = "visibility";
                }
            }

            function selectThemeUI(theme) {
                document.getElementById('settings_theme').value = theme;
                document.querySelectorAll('.theme-btn').forEach(function(btn) {
                    if (btn.dataset.themeVal === theme) {
                        btn.classList.add('border-accent', 'bg-accent-light', 'text-main');
                        btn.classList.remove('border-theme', 'bg-input', 'text-muted');
                    } else {
                        btn.classList.remove('border-accent', 'bg-accent-light', 'text-main');
                        btn.classList.add('border-theme', 'bg-input', 'text-muted');
                    }
                });
                document.documentElement.setAttribute('data-theme', theme);
            }

            // Nombre de archivo de logo (en inglés) para cada color de acento (en español)
            const LOGO_FILE_BY_COLOR = {
                azul: 'blue',
                verde: 'green',
                morado: 'purple',
                naranja: 'orange',
                rosa: 'pink'
            };

            function setAccentColor(color) {
                document.documentElement.setAttribute('data-color', color);
                let favicon = document.getElementById('favicon-link');
                let logoFile = LOGO_FILE_BY_COLOR[color] || 'blue';
                if (favicon) favicon.href = '/static/logos/cicada_' + logoFile + '.svg';
            }

            function selectColorUI(color) {
                document.getElementById('settings_color').value = color;
                document.querySelectorAll('.color-btn').forEach(function(btn) {
                    if (btn.dataset.colorVal === color) {
                        btn.classList.add('border-[2.5px]', 'border-[#1a1b20]', 'ring-[4px]', 'ring-accent-light');
                    } else {
                        btn.classList.remove('border-[2.5px]', 'border-[#1a1b20]', 'ring-[4px]', 'ring-accent-light');
                    }
                });
                setAccentColor(color);
            }

            async function loadSettingsIntoForm() {
                try {
                    let res = await fetch('/api/settings');
                    let data = await res.json();
                    document.getElementById("settings_acoustid_key").value = data.acoustid_api_key || "";
                    document.getElementById("settings_spotify_id").value = data.spotify_client_id || "";
                    document.getElementById("settings_spotify_secret").value = data.spotify_client_secret || "";
                    document.getElementById("settings_plan_c_enabled").checked = !!data.plan_c_enabled;
                    document.getElementById("settings_library_dir").value = data.library_dir || "";
                    document.getElementById("settings_process_input_dir").value = data.process_input_dir || "";
                    document.getElementById("settings_process_output_dir").value = data.process_output_dir || "";
                    selectThemeUI(data.theme || "grafito");
                    selectColorUI(data.color_accent || "azul");
                } catch (e) {
                    console.error("Error cargando ajustes:", e);
                }
            }

            async function saveSettings() {
                let statusEl = document.getElementById("settings-status");
                let btn = document.getElementById("settingsSaveBtn");
                btn.disabled = true;
                statusEl.textContent = t("settings_saving");

                let payload = {
                    acoustid_api_key: document.getElementById("settings_acoustid_key").value,
                    spotify_client_id: document.getElementById("settings_spotify_id").value,
                    spotify_client_secret: document.getElementById("settings_spotify_secret").value,
                    plan_c_enabled: document.getElementById("settings_plan_c_enabled").checked,
                    library_dir: document.getElementById("settings_library_dir").value,
                    process_input_dir: document.getElementById("settings_process_input_dir").value,
                    process_output_dir: document.getElementById("settings_process_output_dir").value,
                    theme: document.getElementById("settings_theme").value,
                    color_accent: document.getElementById("settings_color").value
                };

                try {
                    let res = await fetch('/api/settings', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(payload)
                    });
                    let data = await res.json();
                    if (!res.ok) throw new Error(data.detail || t("error_unknown"));

                    // Reflejar los cambios en los campos ya visibles de otras pestañas, sin recargar la página
                    let inputDirField = document.getElementById("input_dir");
                    if (inputDirField) inputDirField.value = payload.process_input_dir;
                    let outputDirField = document.getElementById("output_dir");
                    if (outputDirField) outputDirField.value = payload.process_output_dir;

                    let libraryBrowseField = document.getElementById("library_browse_dir");
                    if (libraryBrowseField) libraryBrowseField.value = payload.library_dir;
                    let replicateDirField = document.getElementById("library_dir");
                    if (replicateDirField) replicateDirField.value = payload.library_dir;

                    if (payload.library_dir) {
                        await scanLibrary(payload.library_dir);
                    }
                    
                    document.documentElement.setAttribute('data-theme', payload.theme);
                    setAccentColor(payload.color_accent);

                    statusEl.textContent = t("settings_saved");
                    setTimeout(function() { statusEl.textContent = ""; }, 2500);
                } catch (e) {
                    statusEl.textContent = "";
                    alert(t("alert_error_saving_settings") + e.message);
                } finally {
                    btn.disabled = false;
                }
            }

            async function prefillProcessDirsFromSettings() {
                try {
                    let res = await fetch('/api/settings');
                    let data = await res.json();
                    let inputDirField = document.getElementById("input_dir");
                    if (inputDirField && data.process_input_dir) inputDirField.value = data.process_input_dir;
                    let outputDirField = document.getElementById("output_dir");
                    if (outputDirField && data.process_output_dir) outputDirField.value = data.process_output_dir;
                } catch (e) {
                    console.error("Error precargando carpetas de PROCESS:", e);
                }
            }

            function handleSpotifyAuthRedirect() {
                let params = new URLSearchParams(window.location.search);
                let authResult = params.get("spotify_auth");
                if (!authResult) return;

                let reason = params.get("reason") || "";
                window.history.replaceState({}, document.title, window.location.pathname);
                openSettings();

                if (authResult === "error") {
                    setTimeout(function() {
                        let statusEl = document.getElementById("settings-spotify-status");
                        if (statusEl) statusEl.textContent = t("error_prefix") + (reason || t("error_unknown"));
                    }, 300);
                }
            }

            // Vista inicial
            applyLanguage(currentLang);
            showView('process');
            loadLibraryConfig();
            prefillProcessDirsFromSettings();
            
            // Cargar y aplicar tema inicial
            fetch('/api/settings').then(r => r.json()).then(data => {
                document.documentElement.setAttribute('data-theme', data.theme || "grafito");
                setAccentColor(data.color_accent || "azul");
            }).catch(e => console.error("Error loading theme", e));
            handleSpotifyAuthRedirect();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

def print_signature():
    signature = """
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║      ██╗     ██╗  █████╗ ██████╗  ██████╗ ██╗     ██╗                ║
    ║      ██║     ██║ ██╔══██╗██╔══██╗██╔═══██╗██║     ██║                ║
    ║      ██║     ██║ ███████║██████╔╝██║   ██║██║     ██║                ║
    ║ ██╗  ██║██╗  ██║ ██╔══██║██╔══██╗██║   ██║██║     ██║                ║
    ║ ╚█████╔╝╚█████╔╝ ██║  ██║██║  ██║╚██████╔╝███████╗███████╗           ║
    ║  ╚════╝  ╚════╝  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚══════╝           ║
    ║                                                                      ║
    ║   Cicada v1.0.1 - "Dando vida a los píxeles."                    ║
    ║   GitHub: github.com/JJaroll                                         ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """
    try:
        print(signature)
    except UnicodeEncodeError:
        # Si la consola de Windows no soporta los caracteres, simplemente lo ignoramos
        pass

if __name__ == "__main__":
    import threading
    import uvicorn
    import webbrowser
    from tray_icon import run_tray_icon
    import sys
    import os

    print_signature()

    HOST = "127.0.0.1"
    PORT = 8000
    APP_URL = f"http://{HOST}:{PORT}"

    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT))
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    def _quit_app():
        os._exit(0)

    @app.post("/api/shutdown")
    async def shutdown_app():
        threading.Timer(0.5, lambda: os._exit(0)).start()
        return {"message": "Cicada apagada correctamente"}

    # --- FIX DEFINITIVO: Lanzar el navegador de forma independiente ---
    # Esto espera 1 segundo a que el servidor y el Dock estén listos,
    # y luego abre la página sin bloquear la app nativa de macOS.
    threading.Timer(1.0, lambda: webbrowser.open(APP_URL)).start()

    if not run_tray_icon(APP_URL, on_quit=_quit_app):
        server_thread.join()