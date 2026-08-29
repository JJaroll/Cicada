"""Gestión y visualización de fotos almacenadas en el iPod."""
from __future__ import annotations

import hashlib
import io
import logging
import os
import struct
import tempfile
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp", ".tif", ".tiff"}


def _get_cache_dir() -> Path:
    base = Path.home() / ".cache" / "cicada" / "photos"
    try:
        base.mkdir(parents=True, exist_ok=True)
        return base
    except Exception:
        fallback = Path(tempfile.gettempdir()) / "cicada_photos_cache"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


@dataclass
class IpodPhotoInfo:
    photo_id: str
    filename: str
    rel_path: str
    size_bytes: int
    width: int
    height: int
    date_modified: str
    mtime: float


def _get_photos_dir(mount: Path | str) -> Path:
    return Path(mount) / "Photos"


def _get_full_res_dir(mount: Path | str) -> Path:
    return _get_photos_dir(mount) / "Full Resolution"


def _get_photo_db_file(mount: Path | str) -> Path:
    return _get_photos_dir(mount) / "Photo Database"


def _get_ithmb_file(mount: Path | str, fmt: str = "F1007_1.ithmb") -> Path:
    return _get_photos_dir(mount) / "Thumbs" / fmt


def _parse_photo_database(mount: Path | str) -> List[dict]:
    """Parsea el Photo Database binario de Apple para extraer todas las fotos registradas."""
    db_file = _get_photo_db_file(mount)
    if not db_file.is_file():
        return []

    try:
        data = db_file.read_bytes()
    except Exception as exc:
        logger.warning("No se pudo leer Photo Database: %s", exc)
        return []

    photos: List[dict] = []
    pos = 0
    file_len = len(data)

    while pos < file_len - 152:
        if data[pos:pos + 4] == b"mhii":
            try:
                hdr_len, total_len, num_mhod, img_id = struct.unpack("<IIII", data[pos + 4:pos + 20])
                src_id = struct.unpack("<I", data[pos + 20:pos + 24])[0]
                mtime_raw = struct.unpack("<I", data[pos + 28:pos + 32])[0] if pos + 32 <= file_len else 0
                mtime = float(mtime_raw - 2082844800) if mtime_raw > 2082844800 else float(mtime_raw)

                sub_pos = pos + hdr_len
                full_path: Optional[str] = None
                thumb_1007: Optional[Tuple[int, int]] = None
                thumb_1005: Optional[Tuple[int, int]] = None

                for _ in range(num_mhod):
                    if sub_pos + 16 > file_len:
                        break
                    m_tag, m_hdr, m_tot, m_type = struct.unpack("<IIII", data[sub_pos:sub_pos + 16])
                    if m_type == 1:
                        raw_str = data[sub_pos + m_hdr:sub_pos + m_tot]
                        full_path = raw_str.decode("utf-16-le", "replace").rstrip("\x00").replace(":", "/")
                    elif m_type == 2:
                        if sub_pos + 52 <= file_len:
                            fmt_id = struct.unpack("<I", data[sub_pos + 40:sub_pos + 44])[0]
                            offset = struct.unpack("<I", data[sub_pos + 44:sub_pos + 48])[0]
                            size = struct.unpack("<I", data[sub_pos + 48:sub_pos + 52])[0]
                            if fmt_id == 1007:
                                thumb_1007 = (offset, size)
                            elif fmt_id == 1005:
                                thumb_1005 = (offset, size)
                    sub_pos += m_tot

                photos.append({
                    "img_id": img_id,
                    "src_id": src_id,
                    "mtime": mtime if mtime > 0 else db_file.stat().st_mtime,
                    "full_path": full_path,
                    "thumb_1007": thumb_1007,
                    "thumb_1005": thumb_1005,
                })
                pos += total_len
            except Exception:
                pos += 4
        else:
            pos += 1

    return photos


def _decode_ithmb_image(ithmb_file: Path, offset: int, size: int, width: int = 480, height: int = 864) -> Optional[Image.Image]:
    """Decodifica un fotograma RGB565 de un archivo .ithmb a PIL Image en < 1ms."""
    if not ithmb_file.is_file():
        return None
    try:
        with open(ithmb_file, "rb") as f:
            f.seek(offset)
            raw = f.read(size)
        expected_len = width * height * 2
        if len(raw) < expected_len:
            return None

        arr = np.frombuffer(raw[:expected_len], dtype=np.uint16)
        r = (((arr >> 11) & 0x1F) * 255 // 31).astype(np.uint8)
        g = (((arr >> 5) & 0x3F) * 255 // 63).astype(np.uint8)
        b = ((arr & 0x1F) * 255 // 31).astype(np.uint8)
        rgb = np.dstack((r, g, b)).reshape((height, width, 3))
        return Image.fromarray(rgb)
    except Exception as exc:
        logger.warning("Error decodificando imagen ithmb en offset %d: %s", offset, exc)
        return None


def scan_ipod_photos(mount: Path | str) -> List[IpodPhotoInfo]:
    """Escanea el catálogo de fotos del iPod leyendo Photo Database y Full Resolution."""
    mount_path = Path(mount)
    full_res = _get_full_res_dir(mount_path)
    db_items = _parse_photo_database(mount_path)

    photos: List[IpodPhotoInfo] = []
    seen_rel_paths: set[str] = set()

    if db_items:
        for idx, item in enumerate(db_items, start=1):
            img_id = item["img_id"]
            mtime = item["mtime"]
            dt_str = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            full_path = item["full_path"]

            real_file = None
            if full_path:
                clean_full = full_path.lstrip("/")
                candidate = (full_res / clean_full).resolve()
                if candidate.is_file():
                    real_file = candidate

            if real_file:
                rel = str(real_file.relative_to(full_res)).replace(os.sep, "/")
                seen_rel_paths.add(rel.lower())
                photos.append(
                    IpodPhotoInfo(
                        photo_id=f"db:{img_id}",
                        filename=real_file.name,
                        rel_path=rel,
                        size_bytes=real_file.stat().st_size,
                        width=480,
                        height=864,
                        date_modified=dt_str,
                        mtime=mtime,
                    )
                )
            else:
                rel_id = f"db:{img_id}"
                filename = f"Foto_{idx:03d}.jpg"
                photos.append(
                    IpodPhotoInfo(
                        photo_id=rel_id,
                        filename=filename,
                        rel_path=rel_id,
                        size_bytes=829440,
                        width=480,
                        height=864,
                        date_modified=dt_str,
                        mtime=mtime,
                    )
                )

    if full_res.is_dir():
        for root, _dirs, files in os.walk(full_res):
            for fn in files:
                if fn.startswith("._") or fn.startswith("."):
                    continue
                ext = os.path.splitext(fn)[1].lower()
                if ext not in IMAGE_EXTENSIONS:
                    continue

                file_path = Path(root) / fn
                try:
                    rel_path = str(file_path.relative_to(full_res)).replace(os.sep, "/")
                    if rel_path.lower() in seen_rel_paths:
                        continue

                    stat = file_path.stat()
                    dt_str = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

                    photos.append(
                        IpodPhotoInfo(
                            photo_id=rel_path,
                            filename=fn,
                            rel_path=rel_path,
                            size_bytes=stat.st_size,
                            width=0,
                            height=0,
                            date_modified=dt_str,
                            mtime=stat.st_mtime,
                        )
                    )
                except Exception:
                    pass

    photos.sort(key=lambda p: p.mtime, reverse=True)
    return photos


def get_photo_thumbnail_bytes(
    mount: Path | str, rel_path: str, max_size: Tuple[int, int] = (360, 360)
) -> Optional[bytes]:
    """Genera o recupera de caché una miniatura JPEG optimizada."""
    mount_path = Path(mount)
    clean_path = urllib.parse.unquote(rel_path).strip()
    cache_dir = _get_cache_dir()

    if clean_path.startswith("db:"):
        try:
            img_id = int(clean_path.split(":", 1)[1])
        except ValueError:
            return None

        cache_key = hashlib.sha256(f"thumb_db:{img_id}:{max_size}".encode()).hexdigest()
        cache_file = cache_dir / f"{cache_key}.jpg"
        if cache_file.is_file() and cache_file.stat().st_size > 0:
            return cache_file.read_bytes()

        db_items = _parse_photo_database(mount_path)
        item = next((it for it in db_items if it["img_id"] == img_id), None)
        if not item:
            return None

        if item.get("full_path"):
            full_res = _get_full_res_dir(mount_path)
            candidate = (full_res / item["full_path"].lstrip("/")).resolve()
            if candidate.is_file():
                return get_photo_thumbnail_bytes(mount_path, str(candidate.relative_to(full_res)), max_size)

        thumb_spec = item.get("thumb_1007") or item.get("thumb_1005")
        if not thumb_spec:
            return None

        offset, size = thumb_spec
        ithmb_file = _get_ithmb_file(mount_path, "F1007_1.ithmb" if item.get("thumb_1007") else "F1005_1.ithmb")
        w, h = (480, 864) if item.get("thumb_1007") else (80, 80)
        img = _decode_ithmb_image(ithmb_file, offset, size, w, h)
        if not img:
            return None

        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        out_bytes = buf.getvalue()
        try:
            cache_file.write_bytes(out_bytes)
        except Exception:
            pass
        return out_bytes

    full_res = _get_full_res_dir(mount_path)
    clean_rel = clean_path.replace("\\", "/").lstrip("/")
    target = (full_res / clean_rel).resolve()
    try:
        target.relative_to(full_res.resolve())
    except ValueError:
        return None

    if not target.is_file():
        return None

    stat = target.stat()
    cache_key = hashlib.sha256(f"thumb:{target.name}:{stat.st_size}:{stat.st_mtime}:{max_size}".encode()).hexdigest()
    cache_file = cache_dir / f"{cache_key}.jpg"
    if cache_file.is_file() and cache_file.stat().st_size > 0:
        return cache_file.read_bytes()

    try:
        with Image.open(target) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=82, optimize=True)
            thumb_bytes = buf.getvalue()
            try:
                cache_file.write_bytes(thumb_bytes)
            except Exception:
                pass
            return thumb_bytes
    except Exception as exc:
        logger.warning("Error generando miniatura de foto %s: %s", target, exc)
        return None


def get_photo_preview_bytes(
    mount: Path | str, rel_path: str, max_size: Tuple[int, int] = (1920, 1920)
) -> Optional[bytes]:
    """Genera o recupera de caché una versión preview en alta definición para el Lightbox."""
    mount_path = Path(mount)
    clean_path = urllib.parse.unquote(rel_path).strip()
    cache_dir = _get_cache_dir()

    if clean_path.startswith("db:"):
        try:
            img_id = int(clean_path.split(":", 1)[1])
        except ValueError:
            return None

        cache_key = hashlib.sha256(f"prev_db:{img_id}:{max_size}".encode()).hexdigest()
        cache_file = cache_dir / f"{cache_key}.jpg"
        if cache_file.is_file() and cache_file.stat().st_size > 0:
            return cache_file.read_bytes()

        db_items = _parse_photo_database(mount_path)
        item = next((it for it in db_items if it["img_id"] == img_id), None)
        if not item:
            return None

        if item.get("full_path"):
            full_res = _get_full_res_dir(mount_path)
            candidate = (full_res / item["full_path"].lstrip("/")).resolve()
            if candidate.is_file():
                return get_photo_preview_bytes(mount_path, str(candidate.relative_to(full_res)), max_size)

        thumb_spec = item.get("thumb_1007") or item.get("thumb_1005")
        if not thumb_spec:
            return None

        offset, size = thumb_spec
        ithmb_file = _get_ithmb_file(mount_path, "F1007_1.ithmb" if item.get("thumb_1007") else "F1005_1.ithmb")
        w, h = (480, 864) if item.get("thumb_1007") else (80, 80)
        img = _decode_ithmb_image(ithmb_file, offset, size, w, h)
        if not img:
            return None

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90, optimize=True)
        out_bytes = buf.getvalue()
        try:
            cache_file.write_bytes(out_bytes)
        except Exception:
            pass
        return out_bytes

    full_res = _get_full_res_dir(mount_path)
    clean_rel = clean_path.replace("\\", "/").lstrip("/")
    target = (full_res / clean_rel).resolve()
    try:
        target.relative_to(full_res.resolve())
    except ValueError:
        return None

    if not target.is_file():
        return None

    stat = target.stat()
    cache_key = hashlib.sha256(f"prev:{target.name}:{stat.st_size}:{stat.st_mtime}:{max_size}".encode()).hexdigest()
    cache_file = cache_dir / f"{cache_key}.jpg"
    if cache_file.is_file() and cache_file.stat().st_size > 0:
        return cache_file.read_bytes()

    try:
        with Image.open(target) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88, optimize=True)
            preview_bytes = buf.getvalue()
            try:
                cache_file.write_bytes(preview_bytes)
            except Exception:
                pass
            return preview_bytes
    except Exception as exc:
        logger.warning("Error generando preview de foto %s: %s", target, exc)
        return None


def resolve_photo_raw_file(mount: Path | str, rel_path: str) -> Optional[Path]:
    """Resuelve la ruta absoluta del archivo original de la foto si existe."""
    mount_path = Path(mount)
    clean_path = urllib.parse.unquote(rel_path).strip()
    if clean_path.startswith("db:"):
        try:
            img_id = int(clean_path.split(":", 1)[1])
            db_items = _parse_photo_database(mount_path)
            item = next((it for it in db_items if it["img_id"] == img_id), None)
            if item and item.get("full_path"):
                full_res = _get_full_res_dir(mount_path)
                candidate = (full_res / item["full_path"].lstrip("/")).resolve()
                if candidate.is_file():
                    return candidate
        except Exception:
            pass
        return None

    full_res = _get_full_res_dir(mount_path)
    clean_rel = clean_path.replace("\\", "/").lstrip("/")
    target = (full_res / clean_rel).resolve()
    try:
        target.relative_to(full_res.resolve())
    except ValueError:
        return None
    return target if target.is_file() else None

