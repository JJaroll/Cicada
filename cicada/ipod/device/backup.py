"""Creación y restauración de copias de seguridad del iPod."""
from __future__ import annotations

import hashlib
import os
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator, Optional

import zstandard

from cicada.ipod.util import fsfilter
from cicada.ipod.device import write_guard
from cicada.ipod.device.write_guard import (
    IPOD_CONTROL_DIRNAME,
    ITUNES_DIRNAME,
    WriteGuardError,
    assert_within_ipod_control,
    assert_writable,
    resolve_mount,
    safe_rmtree,
)

__all__ = [
    "BackupError",
    "BackupIntegrityError",
    "BackupMode",
    "BackupInfo",
    "UNKNOWN_GUID",
    "KEEP_DB_ONLY",
    "default_backups_dir",
    "create_backup",
    "restore_backup",
    "list_backups",
]

UNKNOWN_GUID = "unknown-device"

KEEP_DB_ONLY = 20

_ZSTD_LEVEL = 10

_DEVICE_DIRNAME = "Device"
_ARTWORK_DIRNAME = "Artwork"
_PHOTOS_DIRNAME = "Photos"


class BackupError(Exception):
    """Base de los errores de backup/restore."""


class BackupIntegrityError(BackupError):
    """El archivo recién creado no supera la verificación de integridad."""


class BackupMode(Enum):
    DB_ONLY = "db-only"
    FULL = "full"

    @classmethod
    def from_str(cls, value: str) -> "BackupMode":
        for m in cls:
            if m.value == value:
                return m
        raise ValueError(f"Modo de backup desconocido: {value!r}")


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    guid: str
    timestamp: str
    mode: BackupMode
    size_bytes: int


def default_backups_dir() -> Path:
    """``~/.cicada/backups/ipod`` (o $CICADA_HOME/backups/ipod)."""
    base = Path(os.environ.get("CICADA_HOME") or (Path.home() / ".cicada"))
    return base / "backups" / "ipod"


def _resolve_guid(mount: Path, guid: Optional[str]) -> str:
    """GUID para el nombre de carpeta; fallback en Fase 0."""
    if guid:
        return guid
    read = write_guard._read_mount_guid(mount)
    return read or UNKNOWN_GUID


def _timestamp(now: Optional[datetime]) -> str:
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _scope_roots(
    mount: Path, mode: BackupMode, *, include_artwork: bool = False
) -> list[tuple[Path, str]]:
    """(ruta_en_disco, arcname) de las raíces que abarca cada modo.

    ``Photos/`` es la única raíz que vive a nivel de volumen, fuera de
    ``iPod_Control/`` — por eso se trata aparte del resto, que siempre
    cuelga de ``control``. Solo ``FULL`` la cubre (si existe): es la
    única raíz que puede tener contenido real de terceros (iTunes/
    Música) sin que Cicada la haya escrito nunca.
    """
    control = mount / IPOD_CONTROL_DIRNAME
    if mode is BackupMode.FULL:
        roots = [(control, IPOD_CONTROL_DIRNAME)]
        photos_root = mount / _PHOTOS_DIRNAME
        if photos_root.is_dir():
            roots.append((photos_root, _PHOTOS_DIRNAME))
        return roots
    subs = [ITUNES_DIRNAME, _DEVICE_DIRNAME]
    if include_artwork:
        subs.append(_ARTWORK_DIRNAME)
    roots = []
    for sub in subs:
        d = control / sub
        if d.is_dir():
            roots.append((d, f"{IPOD_CONTROL_DIRNAME}/{sub}"))
    return roots


def _walk_files(root: Path, arcroot: str) -> Iterator[tuple[Path, str]]:
    """(archivo, arcname) de los archivos regulares bajo ``root``, sin artefactos.

    No desciende a directorios artefacto (``.Trashes``, ``.fseventsd``…).
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not fsfilter.is_macos_artifact(d)]
        rel_dir = os.path.relpath(dirpath, root)
        for fn in filenames:
            if fsfilter.is_macos_artifact(fn):
                continue
            full = Path(dirpath) / fn
            if not full.is_file() or full.is_symlink():
                continue
            rel = fn if rel_dir == "." else f"{rel_dir}/{fn}"
            yield full, f"{arcroot}/{rel}"


def _build_manifest(
    mount: Path, mode: BackupMode, *, include_artwork: bool = False
) -> dict[str, tuple[int, str]]:
    """{arcname: (size, sha256)} de todos los archivos que irán al backup."""
    manifest: dict[str, tuple[int, str]] = {}
    for root, arcroot in _scope_roots(mount, mode, include_artwork=include_artwork):
        for full, arcname in _walk_files(root, arcroot):
            h = hashlib.sha256()
            size = 0
            with open(full, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 16), b""):
                    h.update(chunk)
                    size += len(chunk)
            manifest[arcname] = (size, h.hexdigest())
    return manifest


def _artifact_filter(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
    """Excluye artefactos macOS del tar (y, por corte, sus subárboles)."""
    if fsfilter.is_macos_artifact(Path(tarinfo.name).name):
        return None
    return tarinfo


def _read_archive_manifest(archive: Path) -> dict[str, tuple[int, str]]:
    """Recorre el .tar.zst y devuelve {arcname: (size, sha256)} de los regulares."""
    seen: dict[str, tuple[int, str]] = {}
    dctx = zstandard.ZstdDecompressor()
    with open(archive, "rb") as fh, dctx.stream_reader(fh) as zr:
        with tarfile.open(mode="r|", fileobj=zr) as tar:
            for member in tar:
                if not member.isreg():
                    continue
                h = hashlib.sha256()
                size = 0
                src = tar.extractfile(member)
                assert src is not None
                for chunk in iter(lambda: src.read(1 << 16), b""):
                    h.update(chunk)
                    size += len(chunk)
                seen[member.name] = (size, h.hexdigest())
    return seen


def _verify_integrity(archive: Path, manifest: dict[str, tuple[int, str]]) -> None:
    """Falla si el archivo no es legible o su contenido no coincide con el origen."""
    try:
        seen = _read_archive_manifest(archive)
    except (OSError, tarfile.TarError, zstandard.ZstdError) as exc:
        raise BackupIntegrityError(f"El backup {archive} no se pudo releer: {exc}") from exc
    if seen != manifest:
        faltan = set(manifest) - set(seen)
        sobran = set(seen) - set(manifest)
        difieren = {k for k in set(manifest) & set(seen) if manifest[k] != seen[k]}
        raise BackupIntegrityError(
            f"Integridad del backup fallida: faltan={sorted(faltan)} "
            f"sobran={sorted(sobran)} difieren={sorted(difieren)}"
        )


def create_backup(
    mount: os.PathLike | str,
    mode: BackupMode = BackupMode.DB_ONLY,
    *,
    backups_dir: Optional[os.PathLike | str] = None,
    guid: Optional[str] = None,
    candidates: Optional[Iterable[os.PathLike | str]] = None,
    timestamp: Optional[datetime] = None,
    include_artwork: bool = False,
) -> Path:
    # Crea un respaldo comprimido del estado del iPod.
    resolved = resolve_mount(candidates=candidates if candidates is not None else [mount])
    guid = _resolve_guid(resolved, guid)
    base = Path(backups_dir) if backups_dir is not None else default_backups_dir()
    guid_dir = base / guid
    guid_dir.mkdir(parents=True, exist_ok=True)

    name = f"{guid}_{_timestamp(timestamp)}_{mode.value}.tar.zst"
    archive = guid_dir / name

    manifest = _build_manifest(resolved, mode, include_artwork=include_artwork)

    cctx = zstandard.ZstdCompressor(level=_ZSTD_LEVEL)
    tmp = archive.with_suffix(archive.suffix + ".part")
    try:
        with open(tmp, "wb") as fh:
            with cctx.stream_writer(fh) as zf:
                with tarfile.open(mode="w|", fileobj=zf) as tar:
                    for root, arcroot in _scope_roots(resolved, mode, include_artwork=include_artwork):
                        tar.add(str(root), arcname=arcroot, filter=_artifact_filter)
        os.replace(tmp, archive)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    try:
        _verify_integrity(archive, manifest)
    except BackupIntegrityError:
        archive.unlink(missing_ok=True)
        raise

    if mode is BackupMode.DB_ONLY:
        _rotate_db_only(guid_dir)

    return archive


def _rotate_db_only(guid_dir: Path, keep: int = KEEP_DB_ONLY) -> None:
    """Conserva los ``keep`` backups db-only más recientes; borra el resto.

    El nombre incluye un timestamp ordenable, así que el orden lexicográfico es
    cronológico.
    """
    archives = sorted(guid_dir.glob(f"*_{BackupMode.DB_ONLY.value}.tar.zst"))
    for old in archives[:-keep] if len(archives) > keep else []:
        old.unlink(missing_ok=True)


def restore_backup(
    archive: os.PathLike | str,
    mount: os.PathLike | str,
    *,
    candidates: Optional[Iterable[os.PathLike | str]] = None,
    include_artwork: bool = False,
) -> None:
    # Restaura el iPod a partir de un respaldo.
    archive = Path(archive)
    resolved = resolve_mount(candidates=candidates if candidates is not None else [mount])
    assert_writable(resolved)

    names = _list_member_names(archive)
    archive_paths: set[Path] = set()
    roots: set[Path] = set()
    control = (resolved / IPOD_CONTROL_DIRNAME).resolve()
    photos_root = (resolved / _PHOTOS_DIRNAME).resolve()
    for name in names:
        root_name, top_level_root = _guard_root_for_member(name, control, photos_root)
        dest = resolved / name
        validated = assert_within_ipod_control(dest, resolved, root=root_name)
        archive_paths.add(validated)
        try:
            rel = validated.relative_to(top_level_root)
        except ValueError:
            continue
        if root_name == IPOD_CONTROL_DIRNAME:
            if rel.parts:
                roots.add(control / rel.parts[0])
        else:
            roots.add(photos_root)

    if include_artwork:
        roots.add(control / _ARTWORK_DIRNAME)

    dctx = zstandard.ZstdDecompressor()
    with open(archive, "rb") as fh, dctx.stream_reader(fh) as zr:
        with tarfile.open(mode="r|", fileobj=zr) as tar:
            for member in tar:
                root_name, _top = _guard_root_for_member(member.name, control, photos_root)
                dest = assert_within_ipod_control(resolved / member.name, resolved, root=root_name)
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                elif member.isreg():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    src = tar.extractfile(member)
                    assert src is not None
                    with open(dest, "wb") as out:
                        for chunk in iter(lambda: src.read(1 << 16), b""):
                            out.write(chunk)

    _prune_extras(resolved, roots, archive_paths, photos_root=photos_root)


def _guard_root_for_member(name: str, control: Path, photos_root: Path) -> tuple[str, Path]:
    """(root_name, raíz_resuelta) a usar con ``assert_within_ipod_control``
    para un ``arcname`` del tar — ``Photos/...`` es la única raíz fuera de
    ``iPod_Control/`` (Etapa 6h)."""
    if name == _PHOTOS_DIRNAME or name.startswith(_PHOTOS_DIRNAME + "/"):
        return _PHOTOS_DIRNAME, photos_root
    return IPOD_CONTROL_DIRNAME, control


def _prune_extras(
    mount: Path, roots: set[Path], keep: set[Path], *, photos_root: Optional[Path] = None,
) -> None:
    """Borra bajo cada raíz lo que no esté en ``keep`` (los artefactos se ignoran)."""
    for root in roots:
        if not root.exists():
            continue
        root_name = _PHOTOS_DIRNAME if photos_root is not None and root == photos_root else IPOD_CONTROL_DIRNAME
        for dirpath, dirnames, filenames in os.walk(root, topdown=False):
            for fn in filenames:
                p = Path(dirpath) / fn
                if fsfilter.is_macos_artifact(fn):
                    continue
                if p.resolve() not in keep:
                    assert_within_ipod_control(p, mount, root=root_name)
                    p.unlink(missing_ok=True)
            for dn in dirnames:
                d = Path(dirpath) / dn
                if fsfilter.is_macos_artifact(dn):
                    continue
                if d.resolve() in keep:
                    continue
                try:
                    d.rmdir()
                except OSError:
                    safe_rmtree(d, mount, root=root_name)


def _list_member_names(archive: Path) -> list[str]:
    names: list[str] = []
    dctx = zstandard.ZstdDecompressor()
    with open(archive, "rb") as fh, dctx.stream_reader(fh) as zr:
        with tarfile.open(mode="r|", fileobj=zr) as tar:
            for member in tar:
                names.append(member.name)
    return names


def _parse_backup_name(path: Path) -> Optional[BackupInfo]:
    if not path.name.endswith(".tar.zst"):
        return None
    stem = path.name[: -len(".tar.zst")]
    parts = stem.rsplit("_", 2)
    if len(parts) != 3:
        return None
    guid, ts, mode_str = parts
    try:
        mode = BackupMode.from_str(mode_str)
    except ValueError:
        return None
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return BackupInfo(path=path, guid=guid, timestamp=ts, mode=mode, size_bytes=size)


def list_backups(
    *,
    backups_dir: Optional[os.PathLike | str] = None,
    guid: Optional[str] = None,
) -> list[BackupInfo]:
    # Lista los respaldos disponibles para un GUID.
    base = Path(backups_dir) if backups_dir is not None else default_backups_dir()
    if not base.is_dir():
        return []
    guid_dirs = [base / guid] if guid else [d for d in base.iterdir() if d.is_dir()]
    infos: list[BackupInfo] = []
    for gd in guid_dirs:
        if not gd.is_dir():
            continue
        for path in gd.glob("*.tar.zst"):
            info = _parse_backup_name(path)
            if info is not None:
                infos.append(info)
    infos.sort(key=lambda i: (i.timestamp, i.path.name), reverse=True)
    return infos
