"""Chequeo de tamaño máximo de archivo, consciente del filesystem del volumen.

Adaptado de ``device/storage_safety.py`` de iOpenPod (ver docs/VENDORED.md,
Paquete 9, Etapa 6e), reducido: se porta solo ``require_file_size_supported``.
No se porta ``filesystem_profile.py`` completo (633 líneas: detección
cross-platform de filesystem, sensibilidad a mayúsculas, UUID) — para el
único dato que hace falta aquí, el techo de tamaño de archivo por tipo de
filesystem, alcanza con reusar :func:`cicada.ipod.device.volume_id.filesystem_type`
(ya hace la llamada a ``diskutil info -plist``, un solo campo más del mismo
plist) más una tabla estática.

Verificado contra hardware real: el Nano 7G conectado reporta
``FilesystemType`` = ``"msdos"`` (FAT32) vía ``diskutil`` (2026-08-20) — el
único caso hoy con dispositivo real para probarlo.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from cicada.ipod.device.volume_id import filesystem_type
from cicada.ipod.device.write_guard import WriteGuardError

logger = logging.getLogger(__name__)

__all__ = [
    "FileSizeLimitError",
    "max_file_size_bytes_for_mount",
    "require_file_size_supported",
]


class FileSizeLimitError(WriteGuardError):
    """Un archivo propuesto excede el tamaño máximo soportado por el
    dispositivo o su filesystem."""


#: Techo de tamaño de archivo por tipo de filesystem (bytes), igual que la
#: tabla de iOpenPod (``filesystem_profile.py``, ``_MAX_FILE_SIZE_BYTES``).
_MAX_FILE_SIZE_BYTES: dict[str, int] = {
    "fat": 2 * 1024**3 - 1,
    "fat16": 2 * 1024**3 - 1,
    "fat32": 4 * 1024**3 - 1,
    "msdos": 4 * 1024**3 - 1,
    "msdosfs": 4 * 1024**3 - 1,
    "vfat": 4 * 1024**3 - 1,
}


def max_file_size_bytes_for_mount(mount: str | Path) -> Optional[int]:
    """Techo de tamaño de archivo del filesystem de ``mount``, o ``None`` si
    el tipo de filesystem no se pudo determinar o no está en la tabla
    (filesystems sin límite práctico conocido, como exFAT/HFS+/APFS)."""
    fs_type = filesystem_type(mount)
    if fs_type is None:
        return None
    return _MAX_FILE_SIZE_BYTES.get(fs_type)


def require_file_size_supported(
    file_size: int,
    *,
    max_file_size_bytes: Optional[int],
    display_name: str,
) -> None:
    """Lanza un error legible cuando un archivo no se puede representar."""
    size = max(0, int(file_size or 0))
    limit = int(max_file_size_bytes or 0)
    if limit <= 0 or size <= limit:
        return
    logger.debug(
        "Guardia de tamaño de archivo rechazó la escritura: display_name=%s file_size_bytes=%d max_file_size_bytes=%d",
        display_name, size, limit,
    )
    raise FileSizeLimitError(
        f"{display_name} mide {_format_size(size)}, supera el máximo de "
        f"{_format_size(limit)} soportado por este iPod o su filesystem. "
        "Cicada detuvo la escritura antes de tocar el archivo."
    )


def _format_size(size: int) -> str:
    if size >= 0.1 * 1024**3:
        return f"{size / 1024**3:.1f} GB"
    if size >= 1024**2:
        return f"{size / 1024**2:.1f} MB"
    return f"{size / 1024:.1f} KB"
