"""Resolución de rutas de datos de la aplicación."""
import os
import sys
from pathlib import Path


def get_app_data_dir() -> Path:
    # Obtiene el directorio base de datos de Cicada.
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parents[2]

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    data_dir = base / "Cicada"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
