"""Descarga de audio desde fuentes externas mediante yt-dlp."""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys

from cicada.core.ffmpeg_provisioner import is_ffmpeg_available, resolve_ffmpeg_dir

logger = logging.getLogger(__name__)


class AudioDownloader:
    def __init__(self) -> None:
        self.upgrade_ytdlp()

    def upgrade_ytdlp(self) -> None:
        # Actualiza la herramienta yt-dlp a su última versión.
        try:
            if not getattr(sys, 'frozen', False):
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True
                )
        except Exception as e:
            logger.warning(f"No se pudo auto-actualizar yt-dlp en el inicio: {e}")

    def _sync_download(self, query: str, download_path: str) -> str:
        import yt_dlp

        os.makedirs(download_path, exist_ok=True)

        if not is_ffmpeg_available():
            raise RuntimeError(
                "No se encontró ffmpeg en este equipo. Cicada lo necesita para "
                "convertir el audio descargado. Instalalo (por ejemplo, con "
                "'brew install ffmpeg' en macOS) y volvé a intentar."
            )
        ffmpeg_location = resolve_ffmpeg_dir()

        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
            'playlist_items': '1',
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
        }
        if ffmpeg_location:
            ydl_opts['ffmpeg_location'] = ffmpeg_location

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if not info:
                raise RuntimeError(f"No se obtuvieron resultados de búsqueda para: '{query}'")

            if 'entries' in info:
                if not info['entries']:
                    raise RuntimeError(f"La búsqueda en YouTube no retornó resultados para: '{query}'")
                video_info = info['entries'][0]
            else:
                video_info = info

            temp_filename = ydl.prepare_filename(video_info)

            base_path, _ = os.path.splitext(temp_filename)
            final_path = f"{base_path}.m4a"

            if not os.path.exists(final_path):
                if os.path.exists(temp_filename):
                    final_path = temp_filename
                else:
                    basename = os.path.basename(base_path)
                    matching_files = [
                        os.path.join(download_path, f)
                        for f in os.listdir(download_path)
                        if f.startswith(basename)
                    ]
                    if matching_files:
                        final_path = matching_files[0]
                    else:
                        raise FileNotFoundError(
                            f"No se pudo encontrar el archivo descargado final: {final_path} (temp: {temp_filename})"
                        )

            return os.path.abspath(final_path)

    async def download_audio(self, query: str, download_path: str) -> str:
        # Descarga el audio correspondiente en la ruta indicada.
        return await asyncio.to_thread(self._sync_download, query, download_path)
