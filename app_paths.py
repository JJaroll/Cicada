"""
Resuelve dónde deben vivir los datos persistentes del usuario (.env,
.cicada_config.json, .spotify_token.json).

En modo empaquetado (PyInstaller onefile), Path(__file__) apunta a la carpeta
temporal de extracción (sys._MEIPASS), que se recrea vacía en cada arranque y
se borra al cerrar la app. Guardar ahí credenciales o tokens hace que se
pierdan entre sesiones. Por eso, cuando la app está "congelada" usamos el
directorio estándar de datos de aplicación del sistema operativo; en
desarrollo (ejecutando main.py directamente) seguimos usando la raíz del
proyecto, como antes.
"""

import os
import sys
from pathlib import Path


def get_app_data_dir() -> Path:
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    data_dir = base / "Cicada"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
