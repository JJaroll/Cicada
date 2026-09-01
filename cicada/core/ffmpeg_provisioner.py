"""Localización y descarga automática de ffmpeg cuando no está disponible.

Un .app lanzado desde Finder/Dock en macOS (y equivalentes en otras
plataformas) no hereda el PATH completo de una terminal de login —
launchd solo expone un PATH mínimo del sistema, sin /opt/homebrew/bin.
Por eso yt-dlp puede fallar con "ffmpeg not found" aunque el usuario
tenga ffmpeg instalado y funcionando en su terminal.

Este módulo resuelve ffmpeg en este orden:
  1. Copia ya descargada en get_app_data_dir()/bin (caché entre arranques)
  2. Rutas comunes de instalación del sistema (Homebrew, Windows)
  3. PATH del proceso actual (shutil.which), como último recurso

Si no se encuentra ninguna, descarga un build estático a la carpeta de
caché. Cicada es GPLv3, así que redistribuir binarios GPL de ffmpeg no
genera conflicto de licencia (a diferencia de proyectos con licencias
más permisivas, que sí necesitan perseguir builds LGPL-only).
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Callable, Optional

import httpx

from cicada.core.app_paths import get_app_data_dir

logger = logging.getLogger(__name__)

# Rutas donde suele instalarse ffmpeg fuera del PATH heredado por procesos
# GUI en macOS/Windows (ver docstring del módulo).
_SYSTEM_FALLBACK_DIRS = [
    "/opt/homebrew/bin",  # Homebrew, Apple Silicon
    "/usr/local/bin",     # Homebrew, Intel / Linux
    "/usr/bin",
    r"C:\ffmpeg\bin",
    r"C:\Program Files\ffmpeg\bin",
]

_READY_MARKER = ".ready"

# URLs estables (el asset se reemplaza in-place bajo el tag "latest",
# no cambia de nombre entre versiones de ffmpeg).
_BTBN_BASE = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"
_EVERMEET_INFO = "https://evermeet.cx/ffmpeg/info/{binary}/release"

ProgressCallback = Callable[[str], None]


def _cache_bin_dir() -> Path:
    return get_app_data_dir() / "bin"


def _exe_name(binary: str) -> str:
    return f"{binary}.exe" if sys.platform == "win32" else binary


def _find_system_fallback_dir() -> Optional[str]:
    exe_name = _exe_name("ffmpeg")
    for directory in _SYSTEM_FALLBACK_DIRS:
        candidate = os.path.join(directory, exe_name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return directory
    return None


def resolve_ffmpeg_dir() -> Optional[str]:
    # Devuelve el directorio donde vive un ffmpeg utilizable, o None si
    # no se encontró ninguno (ni en caché, ni en rutas del sistema, ni
    # en el PATH heredado del proceso).
    cache_dir = _cache_bin_dir()
    if (cache_dir / _READY_MARKER).exists():
        return str(cache_dir)

    system_dir = _find_system_fallback_dir()
    if system_dir:
        return system_dir

    if shutil.which("ffmpeg"):
        return None  # yt-dlp ya lo encuentra solo vía PATH, no hace falta forzar nada

    return None


def is_ffmpeg_available() -> bool:
    return resolve_ffmpeg_dir() is not None or shutil.which("ffmpeg") is not None


async def _download_file(url: str, dest: Path, on_progress: Optional[ProgressCallback]) -> None:
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress and total:
                        pct = int(downloaded / total * 100)
                        on_progress(f"Descargando ffmpeg... {pct}%")


def _extract_archive(archive_path: Path, target_dir: Path) -> None:
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(target_dir)
    else:
        with tarfile.open(archive_path) as tf:
            tf.extractall(target_dir)


def _flatten_binaries(extract_dir: Path, target_dir: Path) -> None:
    # Los archivos de BtbN/evermeet.cx traen los binarios dentro de una
    # carpeta anidada (ffmpeg-master-latest-.../bin/ffmpeg[.exe]). Los
    # movemos directo a target_dir para que quede un layout plano y
    # predecible.
    #
    # El build -gpl-shared de Windows no es estático: bin/ trae, junto
    # a ffmpeg.exe/ffprobe.exe, varias .dll de las que dependen en
    # tiempo de ejecución (avcodec-*.dll, avformat-*.dll, etc.) —
    # Windows las busca en el mismo directorio que el .exe al cargarlo.
    # Hay que copiar el CONTENIDO COMPLETO de esa carpeta bin/, no solo
    # los ejecutables sueltos, o ffmpeg.exe queda con dependencias
    # faltantes y no arranca.
    exe_names = {_exe_name("ffmpeg"), _exe_name("ffprobe")}
    bin_dirs = {p.parent for p in extract_dir.rglob("*") if p.is_file() and p.name in exe_names}

    # Solo binarios/librerías, no los .zip/.tar.xz de origen que puedan
    # haber quedado como hermanos del exe (evermeet.cx los extrae
    # directo en extract_dir, sin subcarpeta propia).
    skip_suffixes = {".zip", ".xz", ".tar", ".7z"}
    for bin_dir in bin_dirs:
        for path in bin_dir.iterdir():
            if path.is_file() and path.suffix.lower() not in skip_suffixes:
                dest = target_dir / path.name
                shutil.move(str(path), str(dest))
                dest.chmod(dest.stat().st_mode | 0o111)


async def _download_and_extract(urls: list[str], target_dir: Path, on_progress: Optional[ProgressCallback]) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = target_dir / "_download_tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)

    try:
        for url in urls:
            filename = url.rsplit("/", 1)[-1]
            archive_path = tmp_dir / filename
            await _download_file(url, archive_path, on_progress)
            _extract_archive(archive_path, tmp_dir)

        _flatten_binaries(tmp_dir, target_dir)

        missing = [b for b in ("ffmpeg", "ffprobe") if not (target_dir / _exe_name(b)).exists()]
        if missing:
            raise RuntimeError(f"La descarga de ffmpeg no incluyó: {', '.join(missing)}")

        (target_dir / _READY_MARKER).write_text("ok", encoding="utf-8")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def _resolve_download_urls() -> list[str]:
    if sys.platform == "win32":
        return [f"{_BTBN_BASE}/ffmpeg-master-latest-win64-gpl-shared.zip"]

    if sys.platform == "darwin":
        # evermeet.cx solo publica binarios x86_64 (no hay build ARM64
        # nativo); en Apple Silicon corren igual vía Rosetta 2, que
        # viene preinstalado en la inmensa mayoría de esos equipos.
        async with httpx.AsyncClient(timeout=15.0) as client:
            urls = []
            for binary in ("ffmpeg", "ffprobe"):
                resp = await client.get(_EVERMEET_INFO.format(binary=binary))
                resp.raise_for_status()
                urls.append(resp.json()["download"]["zip"]["url"])
            return urls

    return [f"{_BTBN_BASE}/ffmpeg-master-latest-linux64-gpl-shared.tar.xz"]


async def ensure_ffmpeg(on_progress: Optional[ProgressCallback] = None) -> bool:
    # Se asegura de que haya un ffmpeg utilizable, descargándolo a la
    # caché de la app si hace falta. Devuelve True si quedó disponible
    # (ya sea preexistente o recién descargado), False si la descarga
    # falló (sin conexión, servidor caído, etc.) — Cicada sigue
    # funcionando para todo lo que no dependa de ffmpeg en ese caso.
    if is_ffmpeg_available():
        return True

    try:
        if on_progress:
            on_progress("ffmpeg no encontrado, descargando...")
        urls = await _resolve_download_urls()
        await _download_and_extract(urls, _cache_bin_dir(), on_progress)
        if on_progress:
            on_progress("ffmpeg listo.")
        return True
    except Exception as e:
        logger.warning(f"No se pudo descargar ffmpeg automáticamente: {e}")
        return False
