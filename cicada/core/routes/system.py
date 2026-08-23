"""Router de sistema/UI: selección nativa de carpeta/archivo (osascript en macOS,
PowerShell en Windows) y chequeo de nueva versión contra las releases de GitHub."""
from __future__ import annotations

import re
import subprocess
import sys

import httpx
from fastapi import APIRouter

router = APIRouter()

GITHUB_REPO = "JJaroll/Cicada"


def _parse_version(v: str):
    parts = re.findall(r'\d+', v or "")
    return tuple(int(p) for p in parts) if parts else (0,)


@router.get("/api/select_folder")
def select_folder():
    try:
        if sys.platform == "darwin":
            script = 'tell application "System Events" to activate\n tell application "System Events" to return POSIX path of (choose folder)'
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            path = result.stdout.strip()
            return {"path": path} if path else {"error": "Cancelado"}
        elif sys.platform == "win32":
            script = "Add-Type -AssemblyName System.windows.forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; if ($f.ShowDialog() -eq 'OK') { Write-Output $f.SelectedPath }"
            kwargs = {'creationflags': 0x08000000}
            result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, **kwargs)
            path = result.stdout.strip()
            return {"path": path} if path else {"error": "Cancelado"}
        else:
            return {"error": "Selección nativa no soportada. Copia y pega la ruta."}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/select_file")
def select_file():
    try:
        if sys.platform == "darwin":
            script = 'tell application "System Events" to activate\n tell application "System Events" to return POSIX path of (choose file)'
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            path = result.stdout.strip()
            return {"path": path} if path else {"error": "Cancelado"}
        elif sys.platform == "win32":
            script = "Add-Type -AssemblyName System.windows.forms; $f = New-Object System.Windows.Forms.OpenFileDialog; if ($f.ShowDialog() -eq 'OK') { Write-Output $f.FileName }"
            kwargs = {'creationflags': 0x08000000}
            result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, **kwargs)
            path = result.stdout.strip()
            return {"path": path} if path else {"error": "Cancelado"}
        else:
            return {"error": "Selección nativa no soportada. Copia y pega la ruta."}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/check_update")
async def check_update():
    from cicada.core.main import __version__

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Cicada-App"}
            )
            resp.raise_for_status()
            data = resp.json()

        latest_tag = data.get("tag_name", "")
        latest_version = latest_tag.lstrip("vV")
        return {
            "update_available": _parse_version(latest_version) > _parse_version(__version__),
            "current_version": __version__,
            "latest_version": latest_version,
            "url": data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest"
        }
    except Exception:
        return {"update_available": False}
