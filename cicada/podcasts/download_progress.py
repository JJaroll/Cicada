"""Tracking en memoria de descargas de episodios en curso.

Estado de proceso, no persistente: si el servidor se reinicia a mitad de
una descarga, se pierde el tracking de progreso (el archivo temporal se
limpia igual al reintentar, y el status en SQLite ya refleja la
realidad — ver subscription_store.set_episode_status). Suficiente para
v1: sin infraestructura de cola real, solo asyncio.create_task + polling
desde la UI.

Las entradas quedan en el dict indefinidamente tras terminar (state
"done"/"error") para que el polling pueda leer el resultado final; se
sobrescriben solas cuando ese guid se descarga de nuevo. Sin límite de
tamaño: aceptable para el volumen de episodios que un usuario descarga
en una sesión — si se vuelve un problema real, se le pone un TTL/cap
entonces, no antes.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DownloadProgress:
    guid: str
    state: str = "downloading"  # "downloading" | "done" | "error"
    downloaded_bytes: int = 0
    total_bytes: int = 0
    error: str | None = None


_active: dict[str, DownloadProgress] = {}


def start(guid: str) -> DownloadProgress:
    progress = DownloadProgress(guid=guid)
    _active[guid] = progress
    return progress


def get(guid: str) -> DownloadProgress | None:
    return _active.get(guid)


def is_active(guid: str) -> bool:
    progress = _active.get(guid)
    return progress is not None and progress.state == "downloading"
