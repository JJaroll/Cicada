"""Endpoints de control del proceso y WebSocket de eventos."""
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
    # Inicia el procesamiento de la biblioteca en segundo plano.
    process_control.cancel_requested = False
    background_tasks.add_task(process_library, request.input_dir, request.output_dir)
    return {"message": "Procesamiento iniciado en segundo plano"}


@router.post("/api/cancel")
async def cancel_processing():
    # Solicita la cancelación del procesamiento en curso.
    process_control.cancel_requested = True
    return {"message": "Cancelando..."}


@router.post("/api/debug/simulate_process_done")
async def debug_simulate_process_done(count: int = 300, elapsed_seconds: int = 3725, total_files: Optional[int] = None):
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
    await manager.broadcast(json.dumps({
        "type": "debug_update_available",
        "latest_version": latest_version,
        "url": url
    }))
    return {"status": "ok", "latest_version": latest_version, "url": url}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Gestiona la conexión WebSocket para eventos en tiempo real.
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

