"""Coordinador de sync de Fotos al iPod — Fase 6, Etapa 6h.

Análogo a ``media.py`` (Fase 3): orquesta primitivas ya existentes
(``write_guard``, ``safe_write``/``durability``, ``backup``) en vez de
inventar un coordinador de bajo nivel nuevo. A diferencia de
``media.py``/``create_plan()``/``apply()``, Fotos no tiene relación
alguna con tracks/playlists — su "Photo Database" es un árbol
completamente aparte (``iPod_Control/Photos/``), así que este módulo NO
extiende ``Plan``/``apply()``: es su propio coordinador, con su propia
secuencia de backup/stage/commit/verificación-post-commit/rollback,
calcada de la misma disciplina que ``apply.py`` (Etapa 2c) usa para la
base de datos principal.

Decisiones de alcance ya aprobadas (ver docs/VENDORED.md, Paquete 9):

- **Reescritura completa en cada sync** — sin el camino incremental de
  compactación in-place de iOpenPod (~600 líneas descartadas a propósito,
  misma filosofía que ArtworkDB/Etapa 4c). Cada foto deseada se
  re-codifica desde su archivo fuente en la PC; no hay preservación
  incremental de payloads existentes.
- **Estado off-device** vía :mod:`cicada.ipod.device.photo_mapping`
  (Etapa 6e) — el ``image_id`` de una foto se mantiene estable entre
  syncs por su hash visual, nunca se lee ni se escribe nada de esto en
  el dispositivo.
- **Dedup por hash MD5 de un thumbnail 96x96 EXIF-corregido** — mismo
  algoritmo que ``_image_visual_hash`` de iOpenPod.
- Sin gate de consentimiento de Music.app: ese gate existe porque
  reescribir el iTunesCDB re-firma HASHAB (Etapa 2c/§0.3); Fotos nunca
  toca el iTunesCDB ni HASHAB, así que no hay riesgo análogo que gatear.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image, ImageOps, UnidentifiedImageError

from cicada.ipod.db.artwork.chunks import (
    build_photo_db,
    read_photo_db,
    write_mhba,
    write_mhii_photo,
)
from cicada.ipod.db.artwork.photo_fit import encode_photo_for_format
from cicada.ipod.db.artwork.types import EncodedFormatPayload, PhotoAlbumInput
from cicada.ipod.db.shared.device_time import DeviceTimeContext, read_device_time_context
from cicada.ipod.device import durability
from cicada.ipod.device.backup import BackupMode, create_backup, restore_backup
from cicada.ipod.device.device_info import DeviceInfo
from cicada.ipod.device.path_safety import resolve_device_path
from cicada.ipod.device.photo_mapping import (
    read_photo_mapping,
    write_photo_mapping,
)
from cicada.ipod.device.safe_write import guarded_durable_replace, guarded_durable_unlink
from cicada.ipod.device.storage_safety import max_file_size_bytes_for_mount, require_file_size_supported
from cicada.ipod.device.write_guard import (
    PHOTOS_DIRNAME,
    assert_within_ipod_control,
    assert_writable,
    resolve_mount,
)

logger = logging.getLogger(__name__)

__all__ = [
    "PhotoSyncItem",
    "PhotoSyncResult",
    "PhotoSyncError",
    "UnsafePhotoDeviceError",
    "PhotoPostCommitVerifyError",
    "MIN_PHOTO_ID",
    "image_visual_hash",
    "scan_pc_photos",
    "sync_photos_to_ipod",
]

#: Igual que ``_MIN_PHOTO_ID`` en ``sync/photos.py`` de iOpenPod — los
#: image_id del dispositivo empiezan en 100, no en 0/1.
MIN_PHOTO_ID = 100

_PHOTO_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp"})
#: HEIC/HEIF diferido explícitamente (Etapa 6, ver VENDORED.md) — requiere
#: pillow-heif, no instalado. Caso real (fotos de iPhone), no descartado.

_PHOTO_DB_RELATIVE = Path("Photos") / "Photo Database"
_THUMBS_RELATIVE = Path("Photos") / "Thumbs"
_FULL_RES_RELATIVE = Path("Photos") / "Full Resolution"
#: Subcarpeta propia de Cicada dentro de Full Resolution/ — deliberadamente
#: distinta de "iOpenPod" (el nombre que usa iOpenPod) para no crear
#: ambigüedad sobre qué herramienta escribió cada archivo.
_FULL_RES_SUBDIR = "Cicada"

_MASTER_ALBUM_NAME = "Photo Library"
_BASENAME_MAX_LENGTH = 180


class PhotoSyncError(Exception):
    """Base de los errores del sync de Fotos."""


class UnsafePhotoDeviceError(PhotoSyncError):
    """Procedencia de GUID insegura para escribir (mismo gate que Fase 2)."""


class PhotoPostCommitVerifyError(PhotoSyncError):
    """La verificación post-commit falló tras instalar los archivos en el iPod."""


@dataclass(frozen=True)
class PhotoSyncItem:
    visual_hash: str
    display_name: str
    source_path: str
    size: int
    mtime: int
    album_names: frozenset = field(default_factory=frozenset)


@dataclass(frozen=True)
class PhotoSyncResult:
    success: bool
    backup_path: Optional[Path] = None
    restored_from_backup: bool = False
    error: Optional[str] = None
    photos_written: int = 0
    albums_written: int = 0
    photos_added: int = 0
    photos_removed: int = 0


# ── Hash visual (dedup) ──────────────────────────────────────────────────


def image_visual_hash(img: Image.Image) -> str:
    """MD5 de un thumbnail 96x96 EXIF-corregido — mismo algoritmo que
    ``_image_visual_hash`` de iOpenPod. Deliberadamente MD5 (no criptográfico):
    esto es deduplicación de contenido visual, no integridad de seguridad."""
    normalized = ImageOps.exif_transpose(img).convert("RGB")
    preview = normalized.copy()
    preview.thumbnail((96, 96), Image.Resampling.LANCZOS)
    return hashlib.md5(preview.tobytes()).hexdigest()


def _load_pil_image(path: str | Path) -> Image.Image:
    with Image.open(path) as img:
        img.seek(0)
        loaded = img.copy()
    return ImageOps.exif_transpose(loaded)


def _sanitize_basename(name: str, fallback: str) -> str:
    stem = Path(name).stem if name else fallback
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    cleaned = cleaned[:_BASENAME_MAX_LENGTH].rstrip("._")
    return cleaned or fallback[:_BASENAME_MAX_LENGTH]


# ── Escaneo de la biblioteca local ───────────────────────────────────────


def scan_pc_photos(source_dir: str | Path, *, recurse: bool = True) -> list[PhotoSyncItem]:
    """Escanea ``source_dir`` y devuelve las fotos deduplicadas por hash visual.

    El nombre del subdirectorio inmediato (relativo a ``source_dir``) se
    convierte en nombre de álbum — fotos directamente en la raíz no
    pertenecen a ningún álbum nombrado (solo aparecen en "Photo Library",
    el álbum maestro). Mismo criterio que ``scan_pc_photos`` de iOpenPod.
    """
    root = Path(source_dir).expanduser().resolve()
    if not root.is_dir():
        return []

    files: Iterable[Path] = root.rglob("*") if recurse else root.iterdir()
    by_hash: dict[str, PhotoSyncItem] = {}
    for file_path in files:
        if not file_path.is_file() or file_path.suffix.lower() not in _PHOTO_EXTENSIONS:
            continue
        try:
            img = _load_pil_image(file_path)
        except (UnidentifiedImageError, OSError):
            logger.warning("No se pudo decodificar %s, se omite.", file_path)
            continue

        visual_hash = image_visual_hash(img)
        rel_parent = file_path.parent.relative_to(root)
        album_name = rel_parent.as_posix() if rel_parent.parts else ""

        existing = by_hash.get(visual_hash)
        if existing is not None:
            if album_name:
                by_hash[visual_hash] = existing.__class__(
                    **{**existing.__dict__, "album_names": existing.album_names | {album_name}}
                )
            continue

        stat = file_path.stat()
        by_hash[visual_hash] = PhotoSyncItem(
            visual_hash=visual_hash,
            display_name=file_path.name,
            source_path=str(file_path),
            size=stat.st_size,
            mtime=max(0, int(stat.st_mtime)),
            album_names=frozenset({album_name}) if album_name else frozenset(),
        )
    return list(by_hash.values())


# ── Asignación estable de image_id ───────────────────────────────────────


def _assign_image_ids(
    desired: list[PhotoSyncItem],
    mapping: dict[str, dict],
) -> dict[str, int]:
    """``{visual_hash: image_id}`` — reusa el id existente por hash visual
    (mapa off-device, Etapa 6e) para no reasignar ids en cada sync; asigna
    nuevos ids secuenciales a partir del máximo existente para hashes
    nunca vistos."""
    hash_to_id: dict[str, int] = {}
    max_id = MIN_PHOTO_ID - 1
    for image_id_str, entry in mapping.items():
        try:
            image_id = int(image_id_str)
        except ValueError:
            continue
        max_id = max(max_id, image_id)
        visual_hash = entry.get("visual_hash")
        if visual_hash:
            hash_to_id[visual_hash] = image_id

    assigned: dict[str, int] = {}
    for item in desired:
        if item.visual_hash in hash_to_id:
            assigned[item.visual_hash] = hash_to_id[item.visual_hash]
        else:
            max_id += 1
            assigned[item.visual_hash] = max_id
    return assigned


def _non_master_album_type(device_info: DeviceInfo) -> int:
    """6 en Nano 6G/7G, 2 en el resto — visto empíricamente en
    ``_non_master_album_type_for_device`` de iOpenPod."""
    if device_info.family == "iPod Nano" and device_info.generation in {"6th Gen", "7th Gen"}:
        return 6
    return 2


# ── Codificación + ensamblado del Photo Database ─────────────────────────


def _full_res_photos_relpath(image_id: int, display_name: str) -> str:
    """Ruta relativa a ``Photos/`` (la misma convención que
    ``full_res_storage_path`` de :func:`write_mhii_photo` espera, y la
    misma que ``ParsedPhotoFormatRef.storage_path`` devuelve al leer)."""
    basename = _sanitize_basename(display_name, f"photo{image_id:05d}")
    return str(Path("Full Resolution") / _FULL_RES_SUBDIR / f"{basename}_{image_id:05d}.jpg")


def _thumb_photos_relpath(format_id: int) -> str:
    return str(Path("Thumbs") / f"F{format_id}_1.ithmb")


def _encode_full_res(img: Image.Image) -> bytes:
    import io
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()


def _build_photo_db_contents(
    desired: list[PhotoSyncItem],
    image_ids: dict[str, int],
    *,
    device_info: DeviceInfo,
    time_context: DeviceTimeContext,
) -> tuple[bytes, dict[str, bytes], dict[str, bytes]]:
    """Construye en memoria: (photo_db_bytes, {thumb_relpath: ithmb_bytes},
    {full_res_relpath: jpeg_bytes}). No toca disco.

    ``time_context``: mismo mecanismo probado que usa el resto del
    proyecto para fechas de dispositivo (``build_itunescdb``,
    Etapa 2a/§0.3) — imprescindible. ``created_at``/``digitized_at`` del
    Photo Database son segundos-mac (1904, hora LOCAL del dispositivo),
    no Unix — confirmado contra un Photo Database real escrito por
    Música/iTunes (2026-08-20): el valor crudo decodifica a una fecha
    coherente solo bajo la época de 1904, no Unix (que da un año
    absurdo, ~2092). Mismo patrón de bug documentado que ya mordió 3
    veces con fechas del iTunesCDB — ahora una cuarta vez, con una época
    distinta (1904, no Cocoa/2001), en el único subsistema de Fotos sin
    respaldo SQLite."""
    formats = device_info.capabilities.photo_formats if device_info.capabilities else ()
    if not formats:
        raise PhotoSyncError("El dispositivo no tiene formatos de fotos configurados (supports_photo).")
    format_ids = sorted(fmt.format_id for fmt in formats)

    thumb_buffers: dict[int, bytearray] = {fid: bytearray() for fid in format_ids}
    full_res_files: dict[str, bytes] = {}
    image_sizes: dict[int, int] = {}
    mhii_blobs: list[bytes] = []

    ordered = sorted(desired, key=lambda it: image_ids[it.visual_hash])
    for item in ordered:
        image_id = image_ids[item.visual_hash]
        img = _load_pil_image(item.source_path)

        full_res_bytes = _encode_full_res(img)
        full_res_photos_rel = _full_res_photos_relpath(image_id, item.display_name)
        full_res_files[str(Path("Photos") / full_res_photos_rel)] = full_res_bytes

        thumb_offsets: dict[int, int] = {}
        thumb_payloads: dict[int, EncodedFormatPayload] = {}
        thumb_storage_paths: dict[int, str] = {}
        for fmt in formats:
            payload = encode_photo_for_format(img, fmt)
            buf = thumb_buffers[fmt.format_id]
            thumb_offsets[fmt.format_id] = len(buf)
            buf.extend(payload.data)
            image_sizes[fmt.format_id] = payload.size
            thumb_payloads[fmt.format_id] = payload
            thumb_storage_paths[fmt.format_id] = _thumb_photos_relpath(fmt.format_id)

        full_res_payload = EncodedFormatPayload(
            data=b"", width=0, height=0, size=len(full_res_bytes),
            stride_pixels=0, hpad=0, vpad=0, pixel_format=None,
        )
        mac_timestamp = time_context.unix_to_mac(item.mtime)
        mhii_blobs.append(write_mhii_photo(
            image_id,
            created_at=mac_timestamp,
            digitized_at=mac_timestamp,
            original_size=item.size,
            full_res_payload=full_res_payload,
            full_res_storage_path=full_res_photos_rel,
            thumb_formats=thumb_payloads,
            thumb_offsets=thumb_offsets,
            thumb_storage_paths=thumb_storage_paths,
        ))

    non_master_type = _non_master_album_type(device_info)
    all_ids = sorted(image_ids.values())
    highest_id = max(all_ids, default=MIN_PHOTO_ID - 1)
    master = PhotoAlbumInput(album_id=highest_id + 1, name=_MASTER_ALBUM_NAME, members=tuple(all_ids), album_type=1)
    mhba_blobs = [write_mhba(master)]

    album_names = sorted({name for item in desired for name in item.album_names})
    for index, album_name in enumerate(album_names, start=1):
        members = tuple(sorted(
            image_ids[item.visual_hash] for item in desired if album_name in item.album_names
        ))
        album = PhotoAlbumInput(
            album_id=highest_id + 1 + index, name=album_name, members=members, album_type=non_master_type,
        )
        mhba_blobs.append(write_mhba(album))

    next_img_id = highest_id + len(album_names) + 2
    photo_db = build_photo_db(mhii_blobs, mhba_blobs, format_ids, image_sizes, next_img_id)

    thumb_files = {
        str(_THUMBS_RELATIVE / f"F{fid}_1.ithmb"): bytes(buf)
        for fid, buf in thumb_buffers.items()
    }
    return photo_db, thumb_files, full_res_files


# ── Escritura confinada + durable ────────────────────────────────────────


def _write_staged(mount: Path, relpath: str, data: bytes) -> Path:
    """Escribe ``data`` en ``<mount>/<relpath>.cicada-new`` (confinado a
    ``Photos/`` — fuera de ``iPod_Control/``, ver docstring del módulo —
    con fsync), listo para publicarse con :func:`guarded_durable_replace`."""
    target = assert_within_ipod_control(mount / relpath, mount, root=PHOTOS_DIRNAME)
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.with_name(target.name + ".cicada-new")
    with open(staged, "wb") as f:
        f.write(data)
        durability.flush_written_file(f)
    return staged


def _purge_staging_temps(mount: Path) -> None:
    photos_dir = mount / "Photos"
    if not photos_dir.is_dir():
        return
    for dirpath, _dirnames, filenames in os.walk(photos_dir):
        for fn in filenames:
            if fn.endswith(".cicada-new"):
                p = Path(dirpath) / fn
                try:
                    assert_within_ipod_control(p, mount, root=PHOTOS_DIRNAME)
                    p.unlink(missing_ok=True)
                except Exception as exc:
                    logger.warning("No se pudo purgar temporal %s: %s", p, exc)


# ── Orquestador principal ─────────────────────────────────────────────────


def sync_photos_to_ipod(
    mount: str | Path,
    source_dir: str | Path,
    *,
    device_info: DeviceInfo,
    recurse: bool = True,
    backups_dir: Optional[str | Path] = None,
) -> PhotoSyncResult:
    """Sincroniza la biblioteca de fotos local (``source_dir``) al iPod.

    Reescritura completa (sin camino incremental): cada sync recodifica
    TODAS las fotos deseadas desde su archivo fuente y reconstruye el
    Photo Database + los ``.ithmb`` de miniaturas por completo. Los
    ``image_id`` se mantienen estables entre syncs por hash visual (mapa
    off-device, Etapa 6e) — nunca se lee ni escribe nada de esto en el
    dispositivo.

    Fases (misma disciplina que ``apply.py``, Etapa 2c):
      A. Precondiciones (montaje, escribibilidad, procedencia de GUID).
      B. Backup verificado (``include_photos=True``) antes de cualquier mutación.
      C. Codificar + escribir en staging (``.cicada-new``, con fsync).
      D. Commit por renames — full-res/thumbs primero (lo referenciado),
         Photo Database al final (el ancla, igual que iTunesCDB en apply.py).
      E. Verificación post-commit: relee lo instalado, no confía en lo que
         el código dice haber escrito. Cualquier fallo desde B en adelante
         dispara rollback vía ``restore_backup``.
    """
    resolved_mount = resolve_mount(expected_guid=device_info.firewire_guid, candidates=[mount])
    assert_writable(resolved_mount)
    if not device_info.guid_is_write_safe:
        raise UnsafePhotoDeviceError(
            f"Procedencia de GUID insegura para escribir: {device_info.guid_provenance!r}"
        )
    guid = device_info.firewire_guid
    if not guid:
        raise UnsafePhotoDeviceError("No se pudo determinar el FireWireGUID del dispositivo.")
    time_context = read_device_time_context(resolved_mount)

    desired = scan_pc_photos(source_dir, recurse=recurse)
    mapping = read_photo_mapping(guid)
    image_ids = _assign_image_ids(desired, mapping)

    previous_hashes = {
        entry.get("visual_hash") for entry in mapping.values() if isinstance(entry, dict) and entry.get("visual_hash")
    }
    desired_hashes = {item.visual_hash for item in desired}
    removed_hashes = previous_hashes - desired_hashes
    added_hashes = desired_hashes - previous_hashes

    if not added_hashes and not removed_hashes and mapping:
        # Nada cambió desde el último sync: ni backup ni escritura.
        return PhotoSyncResult(
            success=True, photos_written=len(desired), albums_written=0,
            photos_added=0, photos_removed=0,
        )

    photo_db, thumb_files, full_res_files = _build_photo_db_contents(
        desired, image_ids, device_info=device_info, time_context=time_context,
    )

    max_file_size = max_file_size_bytes_for_mount(resolved_mount)
    for rel, data in {**thumb_files, str(_PHOTO_DB_RELATIVE): photo_db}.items():
        require_file_size_supported(len(data), max_file_size_bytes=max_file_size, display_name=rel)

    # ── Fase B: backup verificado ────────────────────────────────────────
    backup_path = create_backup(
        resolved_mount, mode=BackupMode.DB_ONLY, guid=guid,
        backups_dir=backups_dir, include_photos=True,
    )

    # ── Fase C: staging (.cicada-new, con fsync) ─────────────────────────
    staged: list[tuple[Path, Path]] = []  # (staged_path, final_path)
    try:
        for relpath, data in full_res_files.items():
            staged_path = _write_staged(resolved_mount, relpath, data)
            staged.append((staged_path, resolved_mount / relpath))
        for relpath, data in thumb_files.items():
            staged_path = _write_staged(resolved_mount, relpath, data)
            staged.append((staged_path, resolved_mount / relpath))
        staged_db = _write_staged(resolved_mount, str(_PHOTO_DB_RELATIVE), photo_db)
        staged.append((staged_db, resolved_mount / _PHOTO_DB_RELATIVE))
    except BaseException as exc:
        logger.exception("Fallo durante staging de Fotos: %s", exc)
        for staged_path, _final in staged:
            try:
                staged_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    # ── Fase D: commit por renames (full-res/thumbs antes que la DB) ────
    try:
        for staged_path, final_path in staged:
            guarded_durable_replace(staged_path, final_path, resolved_mount, root=PHOTOS_DIRNAME)
    except BaseException as exc:
        logger.exception("Fallo en commit de Fotos. Rollback inmediato: %s", exc)
        restore_backup(backup_path, resolved_mount, include_photos=True)
        _purge_staging_temps(resolved_mount)
        return PhotoSyncResult(
            success=False, backup_path=backup_path, restored_from_backup=True,
            error=f"Fallo en commit (restaurado): {exc}",
        )

    # ── Fase E: verificación post-commit (relee lo instalado) ───────────
    try:
        db_target = resolved_mount / _PHOTO_DB_RELATIVE
        images, albums = read_photo_db(db_target.read_bytes())
        if len(images) != len(desired):
            raise PhotoPostCommitVerifyError(
                f"Photo Database instalado tiene {len(images)} imágenes, se esperaban {len(desired)}."
            )
        installed_ids = {img.image_id for img in images}
        expected_ids = set(image_ids.values())
        if installed_ids != expected_ids:
            raise PhotoPostCommitVerifyError(
                f"image_id instalados no coinciden con los esperados: "
                f"faltan={sorted(expected_ids - installed_ids)} sobran={sorted(installed_ids - expected_ids)}"
            )
        for img in images:
            if img.full_res is None or not img.full_res.storage_path:
                raise PhotoPostCommitVerifyError(f"Imagen {img.image_id} sin full_res tras el commit.")
            full_res_path = resolve_device_path(
                resolved_mount, Path("Photos") / img.full_res.storage_path, allowed_subtree=_FULL_RES_RELATIVE,
            )
            if not full_res_path.is_file():
                raise PhotoPostCommitVerifyError(f"Falta el archivo full-res de la imagen {img.image_id}: {full_res_path}")
        if len(albums) != 1 + len({name for item in desired for name in item.album_names}):
            raise PhotoPostCommitVerifyError(
                f"Photo Database instalado tiene {len(albums)} álbumes, no coincide con lo esperado."
            )
    except BaseException as exc:
        logger.exception("Verificación post-commit de Fotos fallida. Rollback inmediato: %s", exc)
        restore_backup(backup_path, resolved_mount, include_photos=True)
        _purge_staging_temps(resolved_mount)
        return PhotoSyncResult(
            success=False, backup_path=backup_path, restored_from_backup=True,
            error=f"Verificación post-commit fallida (restaurado): {exc}",
        )

    # ── Éxito: persistir el mapa off-device, limpiar removidas ──────────
    new_mapping = {
        str(image_ids[item.visual_hash]): {
            "visual_hash": item.visual_hash,
            "source_path": item.source_path,
            "display_name": item.display_name,
        }
        for item in desired
    }
    write_photo_mapping(guid, new_mapping)

    for image_id_str, entry in mapping.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("visual_hash") in removed_hashes:
            try:
                image_id = int(image_id_str)
            except ValueError:
                continue
            stale_photos_rel = _full_res_photos_relpath(image_id, entry.get("display_name") or "")
            stale_rel = Path("Photos") / stale_photos_rel
            try:
                guarded_durable_unlink(resolved_mount / stale_rel, resolved_mount, missing_ok=True, root=PHOTOS_DIRNAME)
            except Exception:
                logger.warning("No se pudo borrar el full-res huérfano de la imagen %d.", image_id)

    _purge_staging_temps(resolved_mount)

    return PhotoSyncResult(
        success=True,
        backup_path=backup_path,
        photos_written=len(desired),
        albums_written=len({name for item in desired for name in item.album_names}) + 1,
        photos_added=len(added_hashes),
        photos_removed=len(removed_hashes),
    )
