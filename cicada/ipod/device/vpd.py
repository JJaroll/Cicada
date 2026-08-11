"""Consulta de identidad por USB (SCSI VPD) — dispatcher por plataforma.

Lee la identidad del iPod (FireWireGUID, FamilyID, SerialNumber…) directamente
del hardware por USB, para el caso en que el dispositivo no la tiene en disco
(restaurado desde iTunes: sin `SysInfoExtended`).

- **macOS**: `vpd_iokit` (IOKit SCSITaskLib, ctypes) — sin root, sin pyusb.
- **Linux/Windows**: pendiente (Etapa 2d-b, vía libusb). Devuelve error tipado.

**El fallo NUNCA es silencioso**: cuando no se puede leer, se devuelve la causa
en :attr:`VpdResult.error` (módulo no disponible, IOKit rechazó el
SCSITaskUserClient, dispositivo no encontrado…). Esa causa sube a
`DeviceInfo.usb_error` y a `sources`.

Código propio de Cicada (orquestación). `vpd_iokit` es lo único vendorizado.
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

__all__ = ["VpdResult", "query_vpd"]


@dataclass(frozen=True)
class VpdResult:
    """Resultado de una consulta VPD por USB."""
    data: Optional[dict]        # dict con FireWireGUID/FamilyID/SerialNumber, o None
    error: Optional[str]        # causa cuando data is None (nunca silencioso)
    transport: Optional[str]    # "iokit_scsi_vpd" | ...

    @property
    def ok(self) -> bool:
        return self.data is not None


def query_vpd(*, usb_pid: int = 0, serial_filter: str = "") -> VpdResult:
    """Consulta la VPD del iPod por USB. Devuelve :class:`VpdResult`.

    Nunca lanza: cualquier fallo se reporta en ``error``.
    """
    plat = sys.platform
    if plat == "darwin":
        return _query_macos(usb_pid=usb_pid, serial_filter=serial_filter)
    if plat.startswith("linux"):
        return VpdResult(None, "path libusb (Linux) no implementado aún (Etapa 2d-b)", None)
    if plat.startswith("win"):
        return VpdResult(None, "path Windows no implementado aún (Etapa 2d-b)", None)
    return VpdResult(None, f"USB no soportado en {plat}", None)


def _query_macos(*, usb_pid: int, serial_filter: str) -> VpdResult:
    try:
        from cicada.ipod.device import vpd_iokit
    except Exception as exc:  # framework/ctypes no disponible
        return VpdResult(None, f"IOKit no disponible: {exc}", None)
    try:
        data = vpd_iokit.query_ipod_vpd(usb_pid=usb_pid, serial_filter=serial_filter)
    except Exception as exc:  # el SCSITaskUserClient pudo ser rechazado
        logger.debug("vpd_iokit falló: %s", exc)
        return VpdResult(None, f"IOKit rechazó el SCSITaskUserClient: {exc}", None)
    if not data:
        return VpdResult(None, "dispositivo no encontrado por USB (IOKit)", None)
    return VpdResult(data, None, "iokit_scsi_vpd")
