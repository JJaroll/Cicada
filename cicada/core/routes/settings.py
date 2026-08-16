"""Router de configuración: GET/POST /api/settings — credenciales en .env y
preferencias de la app (tema, acento, directorios, plan C)."""
from __future__ import annotations

import os
from typing import Optional

from dotenv import set_key
from fastapi import APIRouter
from pydantic import BaseModel

from cicada.core import acoustid_fallback
from cicada.core.state import ENV_FILE, load_app_config, save_app_config

router = APIRouter()


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


@router.get("/api/settings")
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


@router.post("/api/settings")
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
