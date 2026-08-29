"""Protección y validación de operaciones de escritura en iPod."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Optional

__all__ = [
    "WriteGuardError",
    "MountNotFoundError",
    "AmbiguousMountError",
    "WrongDeviceError",
    "PathOutsideIpodControlError",
    "ReadOnlyFilesystemError",
    "ProtectedPathError",
    "IPOD_CONTROL_DIRNAME",
    "ITUNES_DIRNAME",
    "PHOTOS_DIRNAME",
    "resolve_mount",
    "assert_within_ipod_control",
    "assert_writable",
    "is_protected_path",
    "assert_deletable",
    "safe_rmtree",
]

IPOD_CONTROL_DIRNAME = "iPod_Control"
ITUNES_DIRNAME = "iTunes"
PHOTOS_DIRNAME = "Photos"


class WriteGuardError(Exception):
    pass


class MountNotFoundError(WriteGuardError):
    pass


class AmbiguousMountError(WriteGuardError):
    pass


class WrongDeviceError(WriteGuardError):
    pass


class PathOutsideIpodControlError(WriteGuardError):
    pass


class ReadOnlyFilesystemError(WriteGuardError):
    pass


class ProtectedPathError(WriteGuardError):
    pass


def _candidate_mounts() -> list[Path]:
    roots: list[Path] = []
    if sys.platform == "darwin":
        roots += _children_of(Path("/Volumes"))
    elif sys.platform.startswith("linux"):
        user = os.environ.get("USER") or ""
        for base in (Path("/media") / user, Path("/run/media") / user,
                     Path("/media"), Path("/mnt")):
            roots += _children_of(base)
    elif sys.platform.startswith("win"):
        from string import ascii_uppercase
        roots += [Path(f"{d}:\\") for d in ascii_uppercase]
    return roots


def _children_of(base: Path) -> list[Path]:
    try:
        return [c for c in base.iterdir()]
    except OSError:
        return []


def _read_mount_guid(mount: Path) -> Optional[str]:
    try:
        from cicada.ipod.device.device_info import read_device_info
        info = read_device_info(mount, use_usb=False)
        return info.firewire_guid
    except Exception:
        return None


def resolve_mount(
    expected_guid: Optional[str] = None,
    *,
    candidates: Optional[Iterable[os.PathLike | str]] = None,
) -> Path:
    # Resuelve y valida el punto de montaje del iPod.
    cands = [Path(c) for c in candidates] if candidates is not None else _candidate_mounts()

    found: list[Path] = []
    for c in cands:
        c = Path(c)
        try:
            if c.is_dir() and (c / IPOD_CONTROL_DIRNAME).is_dir():
                found.append(c)
        except OSError:
            continue

    if not found:
        raise MountNotFoundError(
            "No hay ningún iPod montado (no se encontró ningún volumen con "
            f"'{IPOD_CONTROL_DIRNAME}/')."
        )

    if expected_guid is not None:
        confirmed = [c for c in found if _read_mount_guid(c) == expected_guid]
        if confirmed:
            found = confirmed
        elif any(_read_mount_guid(c) is not None for c in found):
            raise WrongDeviceError(
                f"El iPod montado no coincide con el GUID esperado {expected_guid!r}."
            )

    if len(found) > 1:
        raise AmbiguousMountError(
            f"Hay {len(found)} iPods montados; se requiere expected_guid para elegir."
        )

    return found[0].resolve()


_ALLOWED_ROOTS = frozenset({IPOD_CONTROL_DIRNAME, PHOTOS_DIRNAME})


def _control_dir(mount: os.PathLike | str, root: str = IPOD_CONTROL_DIRNAME) -> Path:
    if root not in _ALLOWED_ROOTS:
        raise ValueError(
            f"root={root!r} no es una raíz segura conocida (válidas: {sorted(_ALLOWED_ROOTS)}). "
            "assert_within_ipod_control() no confina a nombres arbitrarios."
        )
    return (Path(mount) / root).resolve()


def assert_within_ipod_control(
    path: os.PathLike | str,
    mount: os.PathLike | str,
    *,
    root: str = IPOD_CONTROL_DIRNAME,
) -> Path:
    # Valida que la ruta pertenezca a iPod_Control.
    control = _control_dir(mount, root)
    resolved = Path(path).resolve()
    if resolved == control or resolved.is_relative_to(control):
        return resolved
    raise PathOutsideIpodControlError(
        f"La ruta {resolved} está fuera de {control}; escritura rechazada."
    )


def assert_writable(mount: os.PathLike | str) -> None:
    # Comprueba que el sistema de archivos sea escribible.
    resolved_mount = resolve_mount(candidates=[mount])
    control = resolved_mount / IPOD_CONTROL_DIRNAME
    probe_dir = control if control.is_dir() else resolved_mount
    prefix = f".cicada_write_test_{os.getpid()}_"
    try:
        fd, name = tempfile.mkstemp(prefix=prefix, dir=str(probe_dir))
    except OSError as exc:
        raise ReadOnlyFilesystemError(
            f"El volumen {resolved_mount} no admite escritura ({exc.strerror})."
        ) from exc
    try:
        os.close(fd)
    finally:
        try:
            os.unlink(name)
        except OSError:
            pass


def _protected_dirs(mount: os.PathLike | str) -> set[Path]:
    control = Path(mount) / IPOD_CONTROL_DIRNAME
    return {
        control.resolve(),
        (control / ITUNES_DIRNAME).resolve(),
        (Path(mount) / PHOTOS_DIRNAME).resolve(),
    }


def is_protected_path(path: os.PathLike | str, mount: os.PathLike | str) -> bool:
    # Comprueba si el directorio está protegido contra borrado.
    return Path(path).resolve() in _protected_dirs(mount)


def assert_deletable(
    path: os.PathLike | str,
    mount: os.PathLike | str,
    *,
    root: str = IPOD_CONTROL_DIRNAME,
) -> Path:
    # Valida que un directorio pueda ser eliminado seguramente.
    resolved = assert_within_ipod_control(path, mount, root=root)
    if resolved in _protected_dirs(mount):
        raise ProtectedPathError(
            f"Borrado recursivo de {resolved} prohibido de forma absoluta "
            "(sin flag de bypass). Borra su contenido selectivamente si hace falta."
        )
    return resolved


def safe_rmtree(path: os.PathLike | str, mount: os.PathLike | str, *, root: str = IPOD_CONTROL_DIRNAME) -> None:
    # Elimina directorios no protegidos dentro de iPod_Control.
    resolved = assert_deletable(path, mount, root=root)
    assert_writable(mount)
    shutil.rmtree(resolved)
