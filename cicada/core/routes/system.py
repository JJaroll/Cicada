"""Endpoints de integración del sistema y verificación de actualizaciones."""
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
    # Abre el diálogo nativo para seleccionar una carpeta.
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
def select_file(types: str = "", multiple: bool = False):
    # Abre el diálogo nativo para seleccionar archivos.
    try:
        if sys.platform == "darwin":
            if types:
                exts = [t.strip().lstrip(".") for t in types.split(",") if t.strip()]
                type_list = []
                for ext in exts:
                    type_list.append(f'"{ext}"')
                    if ext in ("mp4", "m4v", "mov"):
                        type_list.extend(['"public.mpeg-4"', '"com.apple.quicktime-movie"', '"public.movie"'])
                    elif ext in ("mp3", "m4a", "m4b", "aac", "flac"):
                        type_list.extend(['"public.audio"', '"public.mp3"'])
                    elif ext in ("jpg", "jpeg", "png", "webp", "heic", "bmp"):
                        type_list.extend(['"public.image"', '"public.jpeg"', '"public.png"'])
                type_clause = f' of type {{{", ".join(dict.fromkeys(type_list))}}}'
            else:
                type_clause = ""
            
            multi_clause = " with multiple selections allowed" if multiple else ""
            if multiple:
                script = f'''tell application "System Events" to activate
tell application "System Events"
    set theFiles to (choose file{type_clause}{multi_clause})
    set outPaths to ""
    repeat with f in theFiles
        set outPaths to outPaths & (POSIX path of f) & linefeed
    end repeat
    return outPaths
end tell'''
            else:
                script = f'tell application "System Events" to activate\n tell application "System Events" to return POSIX path of (choose file{type_clause})'

            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            output = result.stdout.strip()
            if not output:
                return {"error": "Cancelado"}
            paths = [p.strip() for p in output.splitlines() if p.strip()]
            return {"path": paths[0] if paths else "", "paths": paths}
        elif sys.platform == "win32":
            filter_str = ""
            if types:
                exts = [f"*.{t.strip().lstrip('.')}" for t in types.split(",") if t.strip()]
                filter_str = f"$f.Filter = 'Archivos compatibles ({';'.join(exts)})|{';'.join(exts)}|Todos los archivos (*.*)|*.*';"
            multi_cmd = "$f.Multiselect = $true;" if multiple else ""
            out_cmd = "Write-Output ($f.FileNames -join '`n')" if multiple else "Write-Output $f.FileName"
            script = f"Add-Type -AssemblyName System.windows.forms; $f = New-Object System.Windows.Forms.OpenFileDialog; {filter_str} {multi_cmd} if ($f.ShowDialog() -eq 'OK') {{ {out_cmd} }}"
            kwargs = {'creationflags': 0x08000000}
            result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, **kwargs)
            output = result.stdout.strip()
            if not output:
                return {"error": "Cancelado"}
            paths = [p.strip() for p in output.splitlines() if p.strip()]
            return {"path": paths[0] if paths else "", "paths": paths}
        else:
            return {"error": "Selección nativa no soportada. Copia y pega la ruta."}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/system/status")
async def get_system_status():
    # Devuelve el estado general y versión del sistema.
    from cicada.core.main import __version__, IPOD_AVAILABLE

    return {
        "status": "connected",
        "app_version": __version__,
        "ipod_module_available": IPOD_AVAILABLE,
    }


@router.get("/api/check_update")
async def check_update():
    # Comprueba si hay actualizaciones disponibles en GitHub.
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

