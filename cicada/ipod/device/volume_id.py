"""Huella del volumen montado — clave del caché GUID off-device sin USB.

El caché de identidad (`~/.cicada`) está indexado por GUID, pero para
consultarlo *sin* GUID (dispositivo restaurado por iTunes) necesitamos una clave
derivable del disco. Esta huella cumple ese papel, con dos niveles de fuerza:

- **strong**: `diskutil info -plist <mount>` → ``VolumeUUID``. En FAT32 macOS lo
  deriva del *Volume Serial Number* del boot sector; `diskutil` hace la lectura
  privilegiada, así que **Cicada no necesita root**. Estable hasta el próximo
  *restore* (que es justo cuando el GUID en disco desaparece — misma granularidad).
- **weak**: `sha256(DeviceNode + VolumeName)`. Último recurso: **no distingue dos
  iPods con el mismo nombre** (dos restaurados por iTunes se llaman ambos "iPod").
  Nunca debe autorizar una escritura de Fase 2 (ver device_info).

Solo lectura. No escribe nada.
"""
from __future__ import annotations

import hashlib
import logging
import plistlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

__all__ = ["VolumeFingerprint", "volume_fingerprint", "filesystem_type"]

_ZERO_UUID = "00000000-0000-0000-0000-000000000000"


@dataclass(frozen=True)
class VolumeFingerprint:
    value: str          # sha256 hex de la fuente elegida
    strength: str       # "strong" | "weak"
    source: str         # p. ej. "diskutil_volumeuuid" | "devicenode+volumename"


def _diskutil_info(mount: Path, *, timeout: float = 10.0) -> dict:
    try:
        proc = subprocess.run(
            ["diskutil", "info", "-plist", str(mount)],
            capture_output=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {}
    if proc.returncode != 0 or not proc.stdout:
        return {}
    try:
        return plistlib.loads(proc.stdout)
    except Exception:
        return {}


def volume_fingerprint(mount: str | Path) -> Optional[VolumeFingerprint]:
    """Huella del volumen en ``mount``, o ``None`` si no se puede derivar.

    Prefiere la fuente **fuerte** (VolumeUUID de diskutil); si no está, cae a la
    **débil** (DeviceNode + VolumeName). En plataformas no-macOS, por ahora solo
    intenta la débil.
    """
    mount = Path(mount)
    if sys.platform == "darwin":
        info = _diskutil_info(mount)
        uuid = str(info.get("VolumeUUID") or "").strip()
        if uuid and uuid != _ZERO_UUID:
            return VolumeFingerprint(
                value=hashlib.sha256(uuid.encode()).hexdigest(),
                strength="strong",
                source="diskutil_volumeuuid",
            )
        # Fallback débil con datos de diskutil.
        node = str(info.get("DeviceNode") or "").strip()
        name = str(info.get("VolumeName") or "").strip()
        if node or name:
            return VolumeFingerprint(
                value=hashlib.sha256(f"{node}\x00{name}".encode()).hexdigest(),
                strength="weak",
                source="devicenode+volumename",
            )
    # No-macOS (o diskutil no dio nada): huella débil por nombre de montaje.
    try:
        name = mount.name
        if name:
            return VolumeFingerprint(
                value=hashlib.sha256(f"mount\x00{name}".encode()).hexdigest(),
                strength="weak",
                source="mountname",
            )
    except OSError:
        pass
    return None


def filesystem_type(mount: str | Path) -> Optional[str]:
    """Código corto de filesystem de ``mount`` (p. ej. ``"msdos"``, ``"exfat"``,
    ``"hfs"``), o ``None`` si no se puede determinar.

    Reusa la misma llamada a ``diskutil info -plist`` de :func:`volume_fingerprint`
    (clave ``FilesystemType`` del plist) en vez de invocar un segundo proceso.
    Verificado contra un Nano 7G real montado: ``FilesystemType`` = ``"msdos"``,
    ``FilesystemName`` = ``"MS-DOS FAT32"`` (2026-08-20). Solo macOS por ahora,
    igual que el resto de este módulo — en otras plataformas devuelve ``None``.
    """
    if sys.platform != "darwin":
        return None
    info = _diskutil_info(Path(mount))
    value = str(info.get("FilesystemType") or "").strip().lower()
    return value or None
