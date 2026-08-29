"""Descarga de episodios de podcast al almacenamiento local."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

log = logging.getLogger(__name__)

_TIMEOUT = 30.0
_CHUNK_SIZE = 64 * 1024

_KNOWN_AUDIO_EXTS = {".mp3", ".m4a", ".m4b", ".aac", ".ogg", ".opus", ".wav", ".flac"}

_CONTENT_TYPE_MAP = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/x-m4b": ".m4b",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "audio/flac": ".flac",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}


def default_podcasts_cache_dir() -> Path:
    # Devuelve el directorio base para caché de podcasts.
    base = Path(os.environ.get("CICADA_HOME") or (Path.home() / ".cicada"))
    return base / "podcasts_cache"


def episode_cache_dir(feed_url: str) -> Path:
    # Obtiene el directorio de caché para el feed.
    url_hash = hashlib.sha256(feed_url.encode()).hexdigest()[:16]
    return default_podcasts_cache_dir() / url_hash


def _safe_filename(guid: str, audio_url: str) -> str:
    parsed = urlparse(audio_url)
    ext = Path(unquote(parsed.path)).suffix.lower()
    if ext not in _KNOWN_AUDIO_EXTS:
        ext = ".mp3"

    safe = re.sub(r"[^\w\-.]", "_", guid)
    if len(safe) > 120:
        safe = hashlib.sha256(guid.encode()).hexdigest()[:24]
    return safe + ext


def _ext_from_content_type(content_type: str) -> str:
    mime = content_type.split(";")[0].strip().lower()
    return _CONTENT_TYPE_MAP.get(mime, "")


class DownloadCancelled(Exception):
    pass


async def download_episode(
    audio_url: str,
    guid: str,
    dest_dir: Path,
    *,
    progress_cb=None,
    is_cancelled=None,
) -> str:
    # Descarga un episodio de podcast al almacenamiento local.
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(guid, audio_url)
    dest_path = dest_dir / filename

    fd, tmp_name = tempfile.mkstemp(dir=str(dest_dir), prefix=".dl-", suffix=".part")
    tmp_path = Path(tmp_name)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
            async with client.stream(
                "GET", audio_url, headers={"User-Agent": "Cicada (Podcast Manager)"}
            ) as resp:
                resp.raise_for_status()

                ct_ext = _ext_from_content_type(resp.headers.get("Content-Type", ""))
                if ct_ext and not dest_path.name.endswith(ct_ext):
                    dest_path = dest_path.with_suffix(ct_ext)

                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0

                with os.fdopen(fd, "wb") as f:
                    async for chunk in resp.aiter_bytes(_CHUNK_SIZE):
                        if is_cancelled is not None and is_cancelled():
                            raise DownloadCancelled(f"Descarga cancelada: {guid}")
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb is not None:
                            progress_cb(downloaded, total)
                    f.flush()
                    os.fsync(f.fileno())

        os.replace(tmp_path, dest_path)
        return str(dest_path.resolve())

    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
