"""Identidad del iPod leída **solo del volumen** — orquestación propia de Cicada.

Reemplaza la orquestación de `scanner`/`info` de iOpenPod (que enreda escritura
al dispositivo y USB en vivo). Aquí:

- **nunca se escribe** en el volumen (solo se leen `SysInfoExtended`/`SysInfo`),
- la **vía USB es opcional** y su ausencia no rompe nada,
- si nada resuelve la familia/generación, se **degrada a un DeviceInfo parcial**,
  nunca a una excepción.

Cascada de identificación: **FamilyID → sufijo de serie → ModelNumStr → USB PID**.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cicada.ipod.device.capabilities import (
    DeviceCapabilities,
    capabilities_for_family_gen,
    checksum_type_for_family_gen,
)
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.family_ids import lookup_family_id
from cicada.ipod.device.lookup import get_model_info, lookup_by_serial
from cicada.ipod.device.sysinfo import (
    normalize_guid,
    parse_sysinfo_extended,
    parse_sysinfo_text,
)

logger = logging.getLogger(__name__)

__all__ = ["DeviceInfo", "identification_methods", "read_device_info"]


@dataclass(frozen=True)
class DeviceInfo:
    mount: Path
    firewire_guid: Optional[str] = None
    family: Optional[str] = None
    generation: Optional[str] = None
    model_number: Optional[str] = None
    serial: Optional[str] = None
    family_id: Optional[int] = None
    capacity: Optional[str] = None
    color: Optional[str] = None
    checksum: Optional[ChecksumType] = None
    capabilities: Optional[DeviceCapabilities] = None
    identified_by: Optional[str] = None   # family_id|serial_suffix|model_number|usb_pid|None
    partial: bool = True
    sources: dict = field(default_factory=dict)


def identification_methods(
    *,
    family_id: Optional[int] = None,
    serial: Optional[str] = None,
    model_number: Optional[str] = None,
) -> dict[str, Optional[tuple[str, str]]]:
    """(familia, generación) que resuelve **cada** vía, o ``None``.

    Auditable y usable para validación cruzada: dos vías que resuelven al mismo
    modelo dan confianza en la tabla.
    """
    out: dict[str, Optional[tuple[str, str]]] = {
        "family_id": None, "serial_suffix": None, "model_number": None,
    }
    entry = lookup_family_id(family_id)
    if entry:
        out["family_id"] = (entry.family, entry.generation)
    if serial:
        res = lookup_by_serial(serial)
        if res:
            _mn, (fam, gen, _cap, _col) = res
            out["serial_suffix"] = (fam, gen)
    if model_number:
        info = get_model_info(model_number)
        if info:
            out["model_number"] = (info[0], info[1])
    return out


def _coerce_family_id(value: object) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _try_usb_identify(mount: Path) -> Optional[tuple[str, str]]:
    """Gancho de identificación por USB en vivo. Vacío hasta la Etapa 2d.

    Devuelve ``None`` si no hay backend/módulos VPD (su ausencia no rompe nada).
    """
    return None


def read_device_info(mount: str | Path, *, use_usb: bool = False) -> DeviceInfo:
    """Lee la identidad del iPod montado en ``mount``. **No escribe nada.**

    Opera sobre la ruta dada (no revalida el montaje: eso es para escrituras).
    ``use_usb=False`` por defecto; el enriquecimiento por USB es opcional.
    """
    mount = Path(mount)
    device_dir = mount / "iPod_Control" / "Device"

    identity: dict = {}
    sie = device_dir / "SysInfoExtended"
    if sie.is_file():
        try:
            identity = parse_sysinfo_extended(sie.read_bytes()).identity
        except Exception as exc:
            logger.warning("SysInfoExtended ilegible en %s: %s", sie, exc)

    sysinfo_txt: dict = {}
    si = device_dir / "SysInfo"
    if si.is_file():
        try:
            sysinfo_txt = parse_sysinfo_text(si.read_text(errors="replace"))
        except Exception as exc:
            logger.warning("SysInfo ilegible en %s: %s", si, exc)

    guid = identity.get("firewire_guid") or normalize_guid(sysinfo_txt.get("FirewireGuid")) or None
    family_id = _coerce_family_id(identity.get("family_id") or sysinfo_txt.get("FamilyID"))
    serial = (identity.get("serial") or sysinfo_txt.get("SerialNumber")
              or sysinfo_txt.get("pszSerialNumber") or None)
    model_number = identity.get("model_number") or sysinfo_txt.get("ModelNumStr") or None

    family = generation = capacity = color = None
    identified_by: Optional[str] = None
    sources: dict = {}

    methods = identification_methods(family_id=family_id, serial=serial, model_number=model_number)

    # Cascada: FamilyID → serial → ModelNumStr.
    for method in ("family_id", "serial_suffix", "model_number"):
        if methods[method] is not None:
            family, generation = methods[method]
            identified_by = method
            sources["family"] = sources["generation"] = method
            break

    # Enriquecimiento de capacidad/color desde la vía serial (si la hay).
    if serial:
        res = lookup_by_serial(serial)
        if res:
            _mn, (_f, _g, cap, col) = res
            capacity, color = cap or None, col or None
            model_number = model_number or _mn

    # USB en vivo, opcional (Etapa 2d). Su ausencia no rompe nada.
    if family is None and use_usb:
        usb_res = _try_usb_identify(mount)
        if usb_res:
            family, generation = usb_res
            identified_by = "usb_pid"
            sources["family"] = sources["generation"] = "usb_pid"

    caps: Optional[DeviceCapabilities] = None
    checksum: Optional[ChecksumType] = None
    if family and generation:
        caps = capabilities_for_family_gen(
            family, generation, capacity=capacity or "", model_number=model_number,
        )
        checksum = caps.checksum if caps else checksum_type_for_family_gen(family, generation)

    if guid:
        sources.setdefault("firewire_guid", "sysinfo_extended")

    return DeviceInfo(
        mount=mount, firewire_guid=guid, family=family, generation=generation,
        model_number=model_number, serial=serial, family_id=family_id,
        capacity=capacity, color=color, checksum=checksum, capabilities=caps,
        identified_by=identified_by, partial=not (family and generation), sources=sources,
    )
