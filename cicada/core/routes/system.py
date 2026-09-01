"""Endpoints de integración del sistema y verificación de actualizaciones."""
from __future__ import annotations

import re
import subprocess
import sys

import httpx
from fastapi import APIRouter

router = APIRouter()

GITHUB_REPO = "JJaroll/Cicada"

# Cicada.exe corre con console=False (--windowed, sin ventana propia):
# los diálogos nativos de Windows (FolderBrowserDialog/OpenFileDialog) se
# lanzan desde un PowerShell hijo que arranca en segundo plano, sin foco.
# Windows bloquea por diseño que un proceso sin foco se lo robe a otro
# (aquí, el navegador) — TopMost solo, SetForegroundWindow directo, e
# incluso AttachThreadInput + BringWindowToTop (el patrón estándar de
# herramientas de automatización de UI) fueron probados y confirmados
# insuficientes en una Windows real: el diálogo seguía apareciendo
# detrás del navegador sin ningún indicio (ni en la barra de tareas).
#
# En vez de seguir peleando para que el diálogo le robe el foco al
# navegador, se minimiza la ventana que actualmente tiene el foco justo
# antes de mostrar el diálogo (y se restaura al cerrarlo) — elimina la
# ventana competidora en vez de forzar el diálogo por encima de ella.
_WIN32_FOCUS_HELPER = (
    "Add-Type -Name Win32 -Namespace FocusHelper -MemberDefinition @'"
    "\n[DllImport(\"user32.dll\")] public static extern IntPtr GetForegroundWindow();"
    "\n[DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);"
    "\n'@\n"
)
_SW_MINIMIZE = 6
_SW_RESTORE = 9


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
            # Ver _WIN32_FOCUS_HELPER arriba: minimiza la ventana en foco
            # (el navegador) antes de mostrar el diálogo, y la restaura al
            # cerrar — evita el problema de foco en vez de pelear contra
            # la restricción de Windows.
            script = (
                "Add-Type -AssemblyName System.windows.forms; "
                f"{_WIN32_FOCUS_HELPER} "
                "$prevFg = [FocusHelper.Win32]::GetForegroundWindow(); "
                f"[FocusHelper.Win32]::ShowWindow($prevFg, {_SW_MINIMIZE}) | Out-Null; "
                "Start-Sleep -Milliseconds 150; "
                "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                "if ($f.ShowDialog() -eq 'OK') { Write-Output $f.SelectedPath }; "
                f"[FocusHelper.Win32]::ShowWindow($prevFg, {_SW_RESTORE}) | Out-Null"
            )
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
            # Ver _WIN32_FOCUS_HELPER arriba: mismo problema de foco que
            # select_folder(), mismo fix (minimizar la ventana en foco en
            # vez de forzar el diálogo por encima de ella).
            focus_setup = (
                f"{_WIN32_FOCUS_HELPER} "
                "$prevFg = [FocusHelper.Win32]::GetForegroundWindow(); "
                f"[FocusHelper.Win32]::ShowWindow($prevFg, {_SW_MINIMIZE}) | Out-Null; "
                "Start-Sleep -Milliseconds 150;"
            )
            restore_cmd = f"[FocusHelper.Win32]::ShowWindow($prevFg, {_SW_RESTORE}) | Out-Null"
            script = f"Add-Type -AssemblyName System.windows.forms; {focus_setup} $f = New-Object System.Windows.Forms.OpenFileDialog; {filter_str} {multi_cmd} if ($f.ShowDialog() -eq 'OK') {{ {out_cmd} }}; {restore_cmd}"
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

