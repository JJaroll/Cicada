"""Lectura del FireWireGUID (8 bytes) del iPod montado, desde el store de
identidad propio de Cicada. Definición única compartida por los firmadores
hashab/hash58/hash72 (antes estaba duplicada y apuntaba a ``iopenpod.device``)."""
from __future__ import annotations

from pathlib import Path


def read_firewire_id(ipod_path: str | Path) -> bytes:
    from cicada.ipod.device.device_info import read_device_info

    info = read_device_info(ipod_path)
    guid = (info.firewire_guid or "").strip()
    if not guid:
        raise ValueError(f"No hay FireWireGUID disponible para {ipod_path}")
    return bytes.fromhex(guid)
