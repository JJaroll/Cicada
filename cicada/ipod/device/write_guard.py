"""Guardia de escritura del módulo iPod — la pieza central de la Fase 0.

**Ninguna operación del módulo iPod puede tocar el volumen sin pasar por aquí.**
Este módulo existe porque es trivial destruir la biblioteca del dispositivo con
una operación de archivos mal apuntada (un ``rmtree`` sobre ``iPod_Control/`` la
borra entera). Aquí viven las invariantes que lo impiden:

1. :func:`resolve_mount` — revalida que el iPod sigue montado *ahora*. El Nano
   7G se desmonta solo durante el uso normal; el resultado **no se cachea nunca**.
2. :func:`assert_within_ipod_control` — rechaza cualquier ruta que, tras resolver
   symlinks y ``..``, caiga fuera de ``<mount>/iPod_Control/``.
3. :func:`assert_writable` — rechaza escribir en un filesystem de solo lectura
   (un iPod HFS+ montado en Linux/Windows, p. ej.).
4. Prohibición **absoluta** (sin flag ni bypass) del borrado recursivo de
   ``iPod_Control/`` y de ``iPod_Control/iTunes/`` — ver :func:`safe_rmtree`.

Las excepciones forman una jerarquía con base :class:`WriteGuardError`, para que
quien las capture distinga "se desmontó" de "ruta inválida" de "solo lectura".

Ver docs/IPOD_INTEGRATION.md (Fase 0 y §6 Riesgos).
"""
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
    """Base de todos los errores del guardia de escritura."""


class MountNotFoundError(WriteGuardError):
    """El iPod no está montado (o se desmontó a mitad de operación)."""


class AmbiguousMountError(WriteGuardError):
    """Hay más de un iPod montado y no se puede desambiguar sin ``expected_guid``."""


class WrongDeviceError(WriteGuardError):
    """El iPod montado no coincide con el ``expected_guid`` solicitado."""


class PathOutsideIpodControlError(WriteGuardError):
    """La ruta cae fuera de ``<mount>/iPod_Control/`` tras resolverla."""


class ReadOnlyFilesystemError(WriteGuardError):
    """El filesystem del volumen no admite escritura."""


class ProtectedPathError(WriteGuardError):
    """Intento de borrado recursivo de un directorio protegido de forma absoluta."""


def _candidate_mounts() -> list[Path]:
    """Puntos de montaje candidatos, dependientes del SO.

    No filtra por iPod todavía; :func:`resolve_mount` selecciona los que tienen
    ``iPod_Control/``. Aislado en su función para poder inyectar candidatos en
    los tests sin depender del hardware.
    """
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
    """Lee el ``FireWireGUID`` del dispositivo montado, o ``None`` si no se puede."""
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
    """Revalida que el iPod sigue montado **ahora** y devuelve su punto de montaje.

    Un montaje válido es un directorio existente que contiene ``iPod_Control/``.
    Cuando el dispositivo se desmonta, su directorio desaparece: por eso el
    resultado **no debe cachearse jamás** — hay que volver a llamar a esta
    función antes de cada operación sobre el disco.

    :param expected_guid: si se indica, exige que el ``FireWireGUID`` del
        dispositivo coincida. (En Fase 0 la lectura del GUID aún no está
        implementada; si no se puede leer, no se puede confirmar la identidad y
        se cae a la heurística de unicidad.)
    :param candidates: iterable de puntos de montaje candidatos; por defecto se
        enumeran los del SO. Existe para inyección en tests.
    :raises MountNotFoundError: si no hay ningún iPod montado.
    :raises AmbiguousMountError: si hay varios y no se pueden desambiguar.
    :raises WrongDeviceError: si ninguno coincide con ``expected_guid``.
    """
    cands = _candidate_mounts() if candidates is None else [Path(c) for c in candidates]

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
    """Exige que ``path`` esté dentro de ``<mount>/<root>/`` (``iPod_Control``
    por default).

    Resuelve symlinks y ``..`` con :meth:`Path.resolve` **antes** de comparar
    (nada de comparar cadenas): un ``../..`` o un symlink que apunte fuera del
    árbol quedan neutralizados. Devuelve la ruta resuelta si es válida.

    :param root: raíz segura, relativa a ``mount``. Por default
        ``iPod_Control`` (todo lo demás del proyecto vive ahí desde Fase 0).
        Fotos (Fase 6, Etapa 6h) es la primera excepción real: el "Photo
        Database" del dispositivo vive en ``<mount>/Photos/``, **fuera** de
        ``iPod_Control/`` — confirmado contra ``sync/photos.py`` de iOpenPod
        y reproducido en vivo (nada bajo ``iPod_Control/`` referencia
        ``Photos/``). Se usa ``root=PHOTOS_DIRNAME`` explícitamente para esos
        casos, nunca por default — ampliar la raíz segura es una decisión
        consciente en cada call site, no un cambio de comportamiento
        retroactivo para el resto del proyecto. **``root`` está cerrado a
        :data:`_ALLOWED_ROOTS`** (``iPod_Control``/``Photos``) — no es un
        parámetro de confinamiento a cualquier subdirectorio; un tercer valor
        lanza ``ValueError`` antes de tocar el filesystem.
    :raises ValueError: si ``root`` no es una de las raíces seguras conocidas.
    :raises PathOutsideIpodControlError: si cae fuera del árbol permitido.
    """
    control = _control_dir(mount, root)
    resolved = Path(path).resolve()
    if resolved == control or resolved.is_relative_to(control):
        return resolved
    raise PathOutsideIpodControlError(
        f"La ruta {resolved} está fuera de {control}; escritura rechazada."
    )


def assert_writable(mount: os.PathLike | str) -> None:
    """Verifica que el volumen admite escritura, o falla.

    Crea y borra un archivo temporal dentro de ``iPod_Control/`` (el único sitio
    donde se nos permite escribir). Un filesystem de solo lectura —un iPod HFS+
    montado en Linux o Windows, por ejemplo— hace fallar la creación.

    :raises ReadOnlyFilesystemError: si no se puede escribir.
    """
    mount_path = Path(mount)
    control = mount_path / IPOD_CONTROL_DIRNAME
    probe_dir = control if control.is_dir() else mount_path
    prefix = f".cicada_write_test_{os.getpid()}_"
    try:
        fd, name = tempfile.mkstemp(prefix=prefix, dir=str(probe_dir))
    except OSError as exc:
        raise ReadOnlyFilesystemError(
            f"El volumen {mount_path} no admite escritura ({exc.strerror})."
        ) from exc
    try:
        os.close(fd)
    finally:
        try:
            os.unlink(name)
        except OSError:
            pass


def _protected_dirs(mount: os.PathLike | str) -> set[Path]:
    """Directorios cuyo borrado recursivo está prohibido de forma absoluta."""
    control = Path(mount) / IPOD_CONTROL_DIRNAME
    return {
        control.resolve(),
        (control / ITUNES_DIRNAME).resolve(),
        (Path(mount) / PHOTOS_DIRNAME).resolve(),
    }


def is_protected_path(path: os.PathLike | str, mount: os.PathLike | str) -> bool:
    """``True`` si ``path`` (resuelto) es un directorio de borrado prohibido."""
    return Path(path).resolve() in _protected_dirs(mount)


def assert_deletable(
    path: os.PathLike | str,
    mount: os.PathLike | str,
    *,
    root: str = IPOD_CONTROL_DIRNAME,
) -> Path:
    """Valida que ``path`` se puede borrar recursivamente. Devuelve la ruta resuelta.

    Doble condición: debe estar dentro de ``<mount>/<root>/`` **y** no ser
    uno de los directorios protegidos (``iPod_Control/``, ``iPod_Control/
    iTunes/``, ``Photos/`` — esta última nunca de forma completa, aunque
    ``root=PHOTOS_DIRNAME``).

    :raises PathOutsideIpodControlError: si está fuera del árbol permitido.
    :raises ProtectedPathError: si es un directorio protegido de forma absoluta.
    """
    resolved = assert_within_ipod_control(path, mount, root=root)
    if resolved in _protected_dirs(mount):
        raise ProtectedPathError(
            f"Borrado recursivo de {resolved} prohibido de forma absoluta "
            "(sin flag de bypass). Borra su contenido selectivamente si hace falta."
        )
    return resolved


def safe_rmtree(path: os.PathLike | str, mount: os.PathLike | str, *, root: str = IPOD_CONTROL_DIRNAME) -> None:
    """Borrado recursivo **guardado**: la única vía permitida para ``rmtree``.

    Revalida ruta (dentro de ``<mount>/<root>/``, no protegida) y que el
    volumen sea escribible antes de tocar nada.
    """
    resolved = assert_deletable(path, mount, root=root)
    assert_writable(mount)
    shutil.rmtree(resolved)
