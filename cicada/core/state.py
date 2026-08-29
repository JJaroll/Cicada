"""Estado y servicios compartidos de la aplicación."""
from __future__ import annotations

import json
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import WebSocket

from cicada.core.app_paths import get_app_data_dir
from cicada.core.audio_processor import AudioProcessor
from cicada.core.download_manager import DownloadManager
from cicada.core.metadata_manager import MetadataManager
from cicada.core.playlist_manager import PlaylistManager
from cicada.core.providers.deezer import DeezerProvider
from cicada.core.providers.youtube_music import YouTubeMusicProvider

APP_DATA_DIR = get_app_data_dir()
ENV_FILE = APP_DATA_DIR / ".env"
load_dotenv(ENV_FILE)
CONFIG_FILE = APP_DATA_DIR / ".cicada_config.json"


def load_app_config() -> Dict[str, Any]:
    # Carga la configuración persistente de la aplicación.
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_app_config(data: Dict[str, Any]) -> None:
    # Guarda la configuración de la aplicación en disco.
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


metadata_manager = MetadataManager()
audio_processor = AudioProcessor()
download_manager = DownloadManager()
playlist_manager = PlaylistManager()
youtube_music_provider = YouTubeMusicProvider()
deezer_provider = DeezerProvider()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        # Acepta y registra una nueva conexión WebSocket.
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        # Envía un mensaje a todas las conexiones activas.
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                pass


manager = ConnectionManager()


class ProcessControl:
    def __init__(self):
        self.cancel_requested = False


process_control = ProcessControl()
