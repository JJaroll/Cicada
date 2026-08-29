"""Descarga de audio desde YouTube vía yt-dlp, compartida entre proveedores de
música (Spotify, YouTube Music, y los que se agreguen después — ver
docs/MUSIC_PROVIDERS.md). Ningún proveedor descarga audio "de sí mismo": todos
resuelven metadata y delegan la descarga real acá, contra YouTube."""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)


class AudioDownloader:
    """Envoltorio sobre yt-dlp: descarga el mejor audio disponible de un video
    o del primer resultado de una búsqueda, y lo deja como .m4a en disco."""

    def __init__(self) -> None:
        self.upgrade_ytdlp()

    def upgrade_ytdlp(self) -> None:
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
        return await asyncio.to_thread(self._sync_download, query, download_path)
