"""Contención de rutas persistidas no confiables dentro de un subárbol aprobado.

Adaptado de ``device/path_safety.py`` de iOpenPod (ver docs/VENDORED.md, Paquete
9, Etapa 6e) — solo ``resolve_device_path``/``UnsafeDevicePathError``, que es lo
que necesita el subsistema de Fotos para resolver rutas como ``"Full
Resolution/iOpenPod/foto_00123.jpg"`` (leídas de la base de datos del
dispositivo, por lo tanto no confiables) sin permitir que un ``..`` o un symlink
las saque de ``Photos/``. ``resolve_host_path``/``UnsafeHostPathError`` de
iOpenPod no se portan: no tienen caso de uso en Cicada todavía.
"""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path


class UnsafeDevicePathError(ValueError):
    """Ruta no confiable persistida en el dispositivo que podría apuntar fuera
    del subárbol permitido."""


def resolve_device_path(
    ipod_root: str | Path,
    device_relative_path: str | Path,
    *,
    allowed_subtree: str | Path,
) -> Path:
    """Resuelve una ruta relativa no confiable del iPod dentro de ``allowed_subtree``.

    Las rutas persistidas por el dispositivo deben ser relativas. Se rechazan
    rutas absolutas ajenas, ``..``, NULs, y cualquier ruta cuyo destino
    resuelto escape por un symlink o reparse point.
    """
    relative_parts = _validated_relative_parts(device_relative_path, "ruta de dispositivo")
    allowed_parts = _validated_relative_parts(allowed_subtree, "subárbol permitido")

    root = Path(ipod_root).resolve(strict=False)
    allowed_lexical = root.joinpath(*allowed_parts)
    candidate_lexical = root.joinpath(*relative_parts)
    if not allowed_lexical.is_relative_to(root):
        raise UnsafeDevicePathError("El subárbol permitido del iPod resuelve fuera del dispositivo")
    if not candidate_lexical.is_relative_to(allowed_lexical):
        raise UnsafeDevicePathError(
            f"La ruta de dispositivo está fuera del subárbol permitido: {device_relative_path!s}",
        )

    _reject_link_or_reparse_components(root, relative_parts)

    allowed = allowed_lexical.resolve(strict=False)
    if not allowed.is_relative_to(root):
        raise UnsafeDevicePathError("El subárbol permitido del iPod resuelve fuera del dispositivo")
    candidate = candidate_lexical.resolve(strict=False)
    if not candidate.is_relative_to(allowed):
        raise UnsafeDevicePathError(
            f"La ruta de dispositivo está fuera del subárbol permitido: {device_relative_path!s}",
        )
    return candidate


def _validated_relative_parts(value: str | Path, label: str) -> tuple[str, ...]:
    raw = os.fspath(value)
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise UnsafeDevicePathError(f"{label} inválida")

    unified = raw.replace("\\", "/")
    if unified.startswith("/") or re.match(r"^[A-Za-z]:", unified):
        raise UnsafeDevicePathError(f"{label.capitalize()} debe ser relativa")

    parts = tuple(unified.split("/"))
    if any(not part or part in {".", ".."} or ":" in part for part in parts):
        raise UnsafeDevicePathError(f"Componente inválido en {label}: {raw}")
    return parts


def _reject_link_or_reparse_components(root: Path, parts: tuple[str, ...]) -> None:
    """Rechaza alias que podrían redirigir una mutación a otro archivo del dispositivo."""
    current = root
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for part in parts:
        current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise UnsafeDevicePathError(
                f"No se pudo inspeccionar de forma segura el componente {current}: {exc}"
            ) from exc
        file_attributes = int(getattr(metadata, "st_file_attributes", 0) or 0)
        if stat.S_ISLNK(metadata.st_mode) or file_attributes & reparse_flag:
            raise UnsafeDevicePathError(
                f"La ruta de dispositivo contiene un symlink o reparse point: {current}"
            )
