"""Rutas y claves off-device de Cicada (``~/.cicada``): raíz de config y hash de
GUID por-dispositivo, centralizados en un único origen para authority, consent y
el marcador de commit."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

__all__ = ["cicada_home", "guid_hash"]


def cicada_home() -> Path:
    return Path(os.environ.get("CICADA_HOME") or (Path.home() / ".cicada"))


def guid_hash(guid: str | bytes) -> str:
    if isinstance(guid, (bytes, bytearray)):
        norm = bytes(guid).hex().upper()
    else:
        norm = str(guid).strip().upper()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
