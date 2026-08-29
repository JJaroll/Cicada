"""Identificación del dispositivo iPod y lectura de información del sistema."""
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

__all__ = [
    "DeviceInfo", "ScanResult", "identification_methods", "read_device_info",
    "discover_ipods",
]


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
    identified_by: Optional[str] = None
    partial: bool = True
    sources: dict = field(default_factory=dict)
    guid_provenance: Optional[str] = None
    usb_error: Optional[str] = None

    @property
    def guid_is_write_safe(self) -> bool:
        """El GUID es de procedencia fuerte (apto para firmar en Fase 2).

        Rechaza ``cache_weak``: un puntero débil no distingue dos iPods con el
        mismo nombre y podría resolver a una identidad ajena.
        """
        return self.guid_provenance in ("disk", "cache_strong", "usb")


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


@dataclass(frozen=True)
class ScanResult:
    """Resultado de escanear volúmenes en busca de iPods (3 estados)."""
    state: str
    ipods: list
    volumes_without_control: list


_IPOD_RESIDUE = ("iPod_Control", "Calendars", "Contacts", "Notes", "Photos")


def _looks_like_ipod_volume(mount: Path) -> bool:
    if "ipod" in mount.name.lower():
        return True
    try:
        entries = {p.name for p in mount.iterdir()}
    except OSError:
        return False
    return any(r in entries for r in _IPOD_RESIDUE)


def discover_ipods(*, candidates: Optional[list] = None) -> ScanResult:
    # Detecta y enumera los dispositivos iPod conectados.
    from cicada.ipod.device import write_guard as wg
    cands = wg._candidate_mounts() if candidates is None else [Path(c) for c in candidates]

    ipods: list = []
    without_control: list = []
    for c in cands:
        c = Path(c)
        try:
            if not c.is_dir():
                continue
            if (c / "iPod_Control").is_dir():
                ipods.append(read_device_info(c))
            elif _looks_like_ipod_volume(c):
                without_control.append(c)
        except OSError:
            continue

    if ipods:
        state = "ready"
    elif without_control:
        state = "no_ipod_control"
    else:
        state = "no_device"
    return ScanResult(state=state, ipods=ipods, volumes_without_control=without_control)


def _coerce_family_id(value: object) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _identity_from_vpd_dict(d: dict) -> tuple[Optional[str], Optional[int], Optional[str], Optional[str]]:
    """(guid, family_id, serial, model_number) desde el dict crudo de VPD/USB."""
    guid = normalize_guid(d.get("FireWireGUID") or d.get("FirewireGuid")) or None
    family_id = _coerce_family_id(d.get("FamilyID"))
    serial = (d.get("SerialNumber") or d.get("pszSerialNumber") or "").strip() or None
    model_number = (d.get("ModelNumStr") or "").strip() or None
    return guid, family_id, serial, model_number


def _synth_sysinfoextended(guid, family_id, serial, model_number) -> bytes:
    """Plist SysInfoExtended mínimo desde los campos de USB, para cachear off-device."""
    import plistlib
    d: dict = {}
    if guid: d["FireWireGUID"] = guid
    if family_id is not None: d["FamilyID"] = int(family_id)
    if serial: d["SerialNumber"] = serial
    if model_number: d["ModelNumStr"] = model_number
    return plistlib.dumps(d)


def read_device_info(mount: str | Path, *, use_usb: bool = False) -> DeviceInfo:
    # Obtiene información técnica y de modelo del iPod.
    mount_path = Path(mount).resolve()
    from cicada.ipod.device import authority
    from cicada.ipod.device.volume_id import volume_fingerprint
    from cicada.ipod.device.vpd import query_vpd

    mount = Path(mount)
    device_dir = mount / "iPod_Control" / "Device"
    sources: dict = {}
    usb_error: Optional[str] = None
    guid_provenance: Optional[str] = None

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
    if guid:
        guid_provenance = "disk"

    fp = volume_fingerprint(mount) if guid is None else None

    def _fill_from_cache(cached_guid: str):
        nonlocal guid, family_id, serial, model_number
        guid = cached_guid
        raw = authority.read_cached_sysinfo_extended(cached_guid)
        if raw:
            try:
                cid = parse_sysinfo_extended(raw).identity
                family_id = family_id or _coerce_family_id(cid.get("family_id"))
                serial = serial or cid.get("serial")
                model_number = model_number or cid.get("model_number")
            except Exception:
                pass

    if guid is None and fp is not None and fp.strength == "strong":
        ptr = authority.read_guid_pointer(fp.value)
        if ptr:
            _fill_from_cache(ptr["firewire_guid"])
            guid_provenance = "cache_strong"

    if guid is None and use_usb:
        vr = query_vpd()
        if vr.ok:
            g2, fid2, ser2, mn2 = _identity_from_vpd_dict(vr.data)
            if g2:
                guid, guid_provenance = g2, "usb"
                family_id = family_id or fid2
                serial = serial or ser2
                model_number = model_number or mn2
                try:
                    authority.store_sysinfo_extended_for_guid(
                        g2, _synth_sysinfoextended(g2, fid2, ser2, mn2))
                    if fp is not None:
                        authority.write_guid_pointer(fp.value, g2, strength=fp.strength)
                except Exception as exc:
                    logger.debug("No se pudo cachear la identidad USB: %s", exc)
            else:
                usb_error = "VPD sin FireWireGUID"
        else:
            usb_error = vr.error
        if usb_error:
            sources["usb"] = usb_error

    if guid is None and fp is not None and fp.strength == "weak":
        ptr = authority.read_guid_pointer(fp.value)
        if ptr:
            _fill_from_cache(ptr["firewire_guid"])
            guid_provenance = "cache_weak"
            sources["firewire_guid_strength"] = "weak"

    family = generation = capacity = color = None
    identified_by: Optional[str] = None
    methods = identification_methods(family_id=family_id, serial=serial, model_number=model_number)
    for method in ("family_id", "serial_suffix", "model_number"):
        if methods[method] is not None:
            family, generation = methods[method]
            identified_by = method
            sources["family"] = sources["generation"] = method
            break
    if serial:
        res = lookup_by_serial(serial)
        if res:
            _mn, (_f, _g, cap, col) = res
            capacity, color = cap or None, col or None
            model_number = model_number or _mn

    caps: Optional[DeviceCapabilities] = None
    checksum: Optional[ChecksumType] = None
    if family and generation:
        caps = capabilities_for_family_gen(
            family, generation, capacity=capacity or "", model_number=model_number,
        )
        checksum = caps.checksum if caps else checksum_type_for_family_gen(family, generation)

    if guid:
        sources.setdefault("firewire_guid", guid_provenance or "sysinfo_extended")

    return DeviceInfo(
        mount=mount, firewire_guid=guid, family=family, generation=generation,
        model_number=model_number, serial=serial, family_id=family_id,
        capacity=capacity, color=color, checksum=checksum, capabilities=caps,
        identified_by=identified_by, partial=not (family and generation), sources=sources,
        guid_provenance=guid_provenance, usb_error=usb_error,
    )
