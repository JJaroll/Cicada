"""Icono en la bandeja del sistema para Cicada."""
import sys
import webbrowser
from pathlib import Path
from typing import Callable

_BASE_DIR = (
    Path(sys._MEIPASS)
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[2]
)
TRAY_ICON_PATH = _BASE_DIR / "static" / "tray_icon.png"


def run_tray_icon(app_url: str, on_quit: Callable[[], None]) -> bool:
    # Inicia el icono interactivo en la bandeja del sistema.
    try:
        import pystray
        from PIL import Image
    except Exception as e:
        print(f"[Cicada] No se pudo iniciar el icono de bandeja del sistema: {e}")
        return False

    try:
        icon_image = Image.open(TRAY_ICON_PATH)
    except Exception as e:
        print(f"[Cicada] No se encontró el icono de bandeja ({TRAY_ICON_PATH}): {e}")
        return False

    def _open_app(icon, item):
        webbrowser.open(app_url)

    def _quit(icon, item):
        icon.stop()
        on_quit()

    menu = pystray.Menu(
        pystray.MenuItem("Abrir Cicada", _open_app, default=True),
        pystray.MenuItem("Salir", _quit),
    )

    icon = pystray.Icon("cicada", icon_image, "Cicada", menu)

    def _setup(icon):
        icon.visible = True
        if sys.platform == "darwin":
            try:
                icon._status_item.button().image().setTemplate_(True)
            except Exception:
                pass

    try:
        icon.run(setup=_setup)
    except Exception as e:
        print(f"[Cicada] El icono de bandeja del sistema se detuvo con un error: {e}")
        return False

    return True
