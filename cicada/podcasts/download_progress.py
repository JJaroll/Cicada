"""Seguimiento en memoria del progreso de descargas de podcasts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DownloadProgress:
    guid: str
    state: str = "downloading"
    downloaded_bytes: int = 0
    total_bytes: int = 0
    error: str | None = None


_active: dict[str, DownloadProgress] = {}


def start(guid: str) -> DownloadProgress:
    # Registra e inicia el seguimiento de una descarga.
    progress = DownloadProgress(guid=guid)
    _active[guid] = progress
    return progress


def get(guid: str) -> DownloadProgress | None:
    # Obtiene el progreso de descarga de un episodio.
    return _active.get(guid)


def is_active(guid: str) -> bool:
    # Comprueba si la descarga del episodio está activa.
    progress = _active.get(guid)
    return progress is not None and progress.state == "downloading"

