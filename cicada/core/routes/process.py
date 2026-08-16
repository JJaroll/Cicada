"""Router del ciclo de proceso y actualizaciones en vivo: inicio/cancelación del
procesado de biblioteca local, endpoints de depuración y el WebSocket /ws que
difunde el progreso a los clientes conectados."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from cicada.core.processing import process_library
from cicada.core.state import manager, process_control

router = APIRouter()


class ProcessRequest(BaseModel):
    input_dir: str
    output_dir: str


@router.post("/api/start")
async def start_processing(request: ProcessRequest, background_tasks: BackgroundTasks):
    process_control.cancel_requested = False
    background_tasks.add_task(process_library, request.input_dir, request.output_dir)
    return {"message": "Procesamiento iniciado en segundo plano"}


@router.post("/api/cancel")
async def cancel_processing():
    process_control.cancel_requested = True
    return {"message": "Cancelando..."}


@router.post("/api/debug/simulate_process_done")
async def debug_simulate_process_done(count: int = 300, elapsed_seconds: int = 3725, total_files: Optional[int] = None):
    """Solo para pruebas locales: emite el mismo mensaje 'done' que el WS envía al
    terminar un procesamiento real, para poder verificar en el navegador el aviso de
    apoyo (>250 canciones) sin tener que procesar una biblioteca real. `total_files`
    permite simular un lote grande con canciones saltadas (total_files > count)."""
    if total_files is None:
        total_files = count
    await manager.broadcast(json.dumps({
        "type": "done",
        "message": "Proceso completado.",
        "report_path": "",
        "count": count,
        "total_files": total_files,
        "elapsed_seconds": elapsed_seconds
    }))
    return {"status": "ok", "count": count, "total_files": total_files, "elapsed_seconds": elapsed_seconds}


@router.post("/api/debug/simulate_update_available")
async def debug_simulate_update_available(latest_version: str = "9.9.9", url: str = "https://github.com/JJaroll/Cicada/releases/latest"):
    """Solo para pruebas locales: hace aparecer de inmediato el banner de "nueva versión
    disponible" en cualquier pestaña abierta de Cicada, sin depender de que exista
    realmente un release más nuevo en GitHub."""
    await manager.broadcast(json.dumps({
        "type": "debug_update_available",
        "latest_version": latest_version,
        "url": url
    }))
    return {"status": "ok", "latest_version": latest_version, "url": url}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
