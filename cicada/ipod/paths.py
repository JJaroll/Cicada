"""Rutas de configuración y cálculo de identificadores para iPod."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

__all__ = ["cicada_home", "guid_hash"]


def cicada_home() -> Path:
    # Obtiene el directorio base de configuración de Cicada.
    return Path(os.environ.get("CICADA_HOME") or (Path.home() / ".cicada"))


def guid_hash(guid: str | bytes) -> str:
    # Calcula el hash identificador a partir del GUID.
    if isinstance(guid, (bytes, bytearray)):
        norm = bytes(guid).hex().upper()
    else:
        norm = str(guid).strip().upper()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]

