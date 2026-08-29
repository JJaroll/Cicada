"""Identificación y huella del volumen del dispositivo iPod."""
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

__all__ = ["VolumeFingerprint", "volume_fingerprint", "get_volume_label"]

_ZERO_UUID = "00000000-0000-0000-0000-000000000000"


@dataclass(frozen=True)
class VolumeFingerprint:
    value: str
    strength: str
    source: str


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
    # Obtiene la huella digital del volumen montado.
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
        node = str(info.get("DeviceNode") or "").strip()
        name = str(info.get("VolumeName") or "").strip()
        if node or name:
            return VolumeFingerprint(
                value=hashlib.sha256(f"{node}\x00{name}".encode()).hexdigest(),
                strength="weak",
                source="devicenode+volumename",
            )
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


def get_volume_label(mount: str | Path | None) -> Optional[str]:
    # Obtiene la etiqueta del volumen en el sistema.
    if not mount:
        return None
    mount = Path(mount)

    if sys.platform.startswith("win"):
        try:
            import ctypes
            drive_str = str(mount)
            if not drive_str.endswith("\\"):
                drive_str += "\\"
            vol_buf = ctypes.create_unicode_buffer(1024)
            fs_buf = ctypes.create_unicode_buffer(1024)
            serial_num = ctypes.c_ulong()
            max_len = ctypes.c_ulong()
            flags = ctypes.c_ulong()

            res = ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(drive_str),
                vol_buf,
                ctypes.sizeof(vol_buf),
                ctypes.byref(serial_num),
                ctypes.byref(max_len),
                ctypes.byref(flags),
                fs_buf,
                ctypes.sizeof(fs_buf),
            )
            if res:
                label = vol_buf.value.strip()
                if label:
                    return label
        except Exception:
            pass

    if sys.platform == "darwin":
        try:
            mount_str = str(mount.resolve() if mount.exists() else mount)
            if mount_str.startswith("/Volumes/") and mount.name and mount.name != "Volumes":
                return mount.name
            dinfo = _diskutil_info(mount)
            vname = str(dinfo.get("VolumeName") or "").strip()
            if vname:
                return vname
        except Exception:
            pass

    if sys.platform.startswith("linux"):
        try:
            mount_str = str(mount)
            if (mount_str.startswith("/media/") or mount_str.startswith("/run/media/")) and mount.name:
                return mount.name
        except Exception:
            pass

    return None
