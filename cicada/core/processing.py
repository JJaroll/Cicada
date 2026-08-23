"""Pipeline de proceso en segundo plano (servicio, no router): procesado de
biblioteca local y descargas de Spotify, con reporte de progreso vía WebSocket y
soporte de cancelación. Compartido por los routers process y spotify."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List

from cicada.core.state import (
    audio_processor,
    download_manager,
    load_app_config,
    manager,
    metadata_manager,
    process_control,
)

logger = logging.getLogger(__name__)


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
        if process_control.cancel_requested:
            await manager.broadcast(json.dumps({"type": "error", "message": "Proceso cancelado por el usuario."}))
            break

        current = idx + 1

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

        if current < total_files:
            await log_callback("⏳ Esperando 3 segundos entre canciones (Programación defensiva)...")
            await asyncio.sleep(3)

    report_path = output_path / "cicada_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)

    if process_control.cancel_requested:
        await manager.broadcast(json.dumps({"type": "done", "message": "Proceso detenido. (Reporte parcial guardado)", "report_path": str(report_path)}))
    else:
        tagged_count = len(report['successes']) + len(report['incomplete'])
        elapsed_seconds = round(time.time() - start_time)
        await manager.broadcast(json.dumps({
            "type": "done",
            "message": "Proceso completado.",
            "report_path": str(report_path),
            "count": tagged_count,
            "total_files": total_files,
            "elapsed_seconds": elapsed_seconds
        }))


async def _download_and_tag_tracks(tracks: List[Dict[str, Any]], output_dir: str):
    """ Descarga (YouTube Music) e inyecta metadata a una lista ya resuelta de tracks de Spotify. """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    total = len(tracks)
    await manager.broadcast(json.dumps({"type": "info", "message": f"Se van a descargar {total} pista(s)."}))

    for i, track in enumerate(tracks):
        if process_control.cancel_requested:
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

    if process_control.cancel_requested:
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
