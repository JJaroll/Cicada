"""Autoridad de SysInfo — reimplementación propia de Cicada (off-device).

iOpenPod cachea la procedencia de la identidad del dispositivo en un archivo
``iOpenPodSysInfoAuthority`` **dentro de** ``iPod_Control/Device/``, y llega a
reescribir ``SysInfo``/``SysInfoExtended`` en el dispositivo. Eso hace que
Music.app considere el iPod corrupto y pida restaurarlo.

Cicada **no escribe nada en el volumen** por este camino. Esta reimplementación
cumple la misma interfaz que espera ``info.py`` (``read_authority``,
``check_authority_coverage``, ``update_sysinfo``, ``cache_sysinfo_extended`` +
``SOURCE_RANK``/``SYSINFO_FIELDS``), pero persiste todo en ``~/.cicada/``:

    ~/.cicada/sysinfo/<sha256(guid)[:16]>/
    ├── authority.json     # procedencia; incluye el GUID real dentro
    └── SysInfoExtended     # payload cacheado (bytes del plist)

El caché se indexa por **FireWireGUID** (no por punto de montaje): el mismo iPod
puede montarse en rutas distintas, y el usuario puede tener varios dispositivos.
El nombre de carpeta es ``sha256(guid)[:16]`` para no exponer el identificador
del dispositivo en rutas, logs ni capturas; el GUID real vive dentro del JSON.

Ver docs/IPOD_INTEGRATION.md §0.2. Atribución en cicada/ipod/NOTICE (la lógica
de ranking/procedencia y las tablas derivan de iOpenPod, MIT).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import plistlib
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover - solo tipos; info.py llega en Etapa 2b
    from cicada.ipod.device.info import DeviceInfo

logger = logging.getLogger(__name__)

__all__ = [
    "SOURCE_RANK",
    "SYSINFO_FIELDS",
    "AUTHORITY_FILENAME",
    "FOREIGN_AUTHORITY_FILENAME",
    "read_authority",
    "check_authority_coverage",
    "update_sysinfo",
    "cache_sysinfo_extended",
    "clean_foreign_authority",
    "read_guid_pointer",
    "write_guid_pointer",
    "read_cached_sysinfo_extended",
]

#: Nombre de nuestro JSON de autoridad (off-device).
AUTHORITY_FILENAME = "authority.json"

#: Archivo de autoridad de iOpenPod en el dispositivo — ajeno, otro formato.
FOREIGN_AUTHORITY_FILENAME = "iOpenPodSysInfoAuthority"

# ── Ranking de procedencia (de más a menos fiable) ─────────────────────
_SOURCE_ORDER: list[str] = [
    # Seguras: sondeos de hardware en vivo
    "scsi_vpd", "windows_scsi", "linux_scsi", "sysfs_vpd", "udev_scsi_id",
    "usb_vendor", "vpd", "iokit", "ioctl", "device_tree", "ioreg", "sysfs",
    "udev", "wmi",
    # Adivinanzas: lookups, derivaciones, archivos
    "itunes", "serial_lookup", "usb_pid", "disk_size", "model_table",
    "inferred", "sysinfo_extended", "sysinfo", "hashing", "unknown",
]
SOURCE_RANK: dict[str, int] = {src: i for i, src in enumerate(_SOURCE_ORDER)}
"""source → rango (menor = más fiable)."""

_WORST_RANK: int = len(_SOURCE_ORDER)
_SURE_THRESHOLD: int = SOURCE_RANK["itunes"]  # rango < esto = fuente "segura"

# ── Mapeo clave SysInfo ↔ campo DeviceInfo ─────────────────────────────
SYSINFO_FIELDS: list[tuple[str, str]] = [
    ("pszSerialNumber", "serial"),
    ("FirewireGuid", "firewire_guid"),
    ("visibleBuildID", "firmware"),
    ("BoardHwName", "board"),
    ("ModelNumStr", "model_number"),
    ("FamilyID", "family_id"),
    ("UpdaterFamilyID", "updater_family_id"),
    ("ModelFamily", "model_family"),
    ("Generation", "generation"),
    ("Capacity", "capacity"),
    ("Color", "color"),
    ("USBProductID", "usb_pid"),
]

_CORE_FIELDS: frozenset[str] = frozenset({
    "pszSerialNumber", "FirewireGuid", "ModelNumStr",
})


# ──────────────────────────────────────────────────────────────────────
# Raíz del caché (off-device) — override por CICADA_HOME para tests
# ──────────────────────────────────────────────────────────────────────
def _cicada_home() -> Path:
    return Path(os.environ.get("CICADA_HOME") or (Path.home() / ".cicada"))


def _sysinfo_cache_root() -> Path:
    return _cicada_home() / "sysinfo"


def _cache_dir_for_guid(guid: str) -> Path:
    digest = hashlib.sha256(guid.encode("utf-8")).hexdigest()[:16]
    return _sysinfo_cache_root() / digest


# ──────────────────────────────────────────────────────────────────────
# Índice puntero: huella de volumen -> GUID (para resolver sin USB)
# ──────────────────────────────────────────────────────────────────────
def _pointer_path(volume_fp: str) -> Path:
    digest = hashlib.sha256(volume_fp.encode("utf-8")).hexdigest()[:16]
    return _sysinfo_cache_root() / "index" / f"{digest}.json"


def read_guid_pointer(volume_fp: str) -> Optional[dict]:
    """Devuelve ``{"firewire_guid", "strength"}`` para una huella de volumen, o None."""
    path = _pointer_path(volume_fp)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(data, dict) and data.get("firewire_guid"):
        return data
    return None


def write_guid_pointer(volume_fp: str, guid: str, *, strength: str) -> None:
    """Guarda el puntero huella_de_volumen -> GUID (off-device)."""
    path = _pointer_path(volume_fp)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    payload = {"firewire_guid": guid, "strength": strength, "updated": _now()}
    tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def read_cached_sysinfo_extended(guid: str) -> Optional[bytes]:
    """Bytes del SysInfoExtended cacheado off-device para ``guid``, o None."""
    path = _cache_dir_for_guid(guid) / "SysInfoExtended"
    try:
        return path.read_bytes() if path.is_file() else None
    except OSError:
        return None


def store_sysinfo_extended_for_guid(guid: str, raw_xml: bytes | str) -> None:
    """Guarda el SysInfoExtended por GUID explícito (para el caso USB, donde el
    dispositivo no lo tiene en disco). Off-device, nunca en el volumen."""
    data = _normalise_sysinfo_extended(raw_xml)
    if not data:
        return
    directory = _cache_dir_for_guid(guid)
    directory.mkdir(parents=True, exist_ok=True)
    payload = directory / "SysInfoExtended"
    tmp = payload.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, payload)


# ──────────────────────────────────────────────────────────────────────
# Lectura de identidad del dispositivo (para indexar por GUID)
# ──────────────────────────────────────────────────────────────────────
def _device_dir(ipod_path: str | os.PathLike) -> Path:
    return Path(ipod_path) / "iPod_Control" / "Device"


def _normalise_guid(raw: object) -> Optional[str]:
    val = str(raw or "").strip().rstrip("\x00")
    if val.startswith(("0x", "0X")):
        val = val[2:]
    val = val.upper()
    return val or None


def _read_device_guid(ipod_path: str | os.PathLike) -> Optional[str]:
    """FireWireGUID del dispositivo montado en ``ipod_path``, o ``None``.

    Prueba SysInfoExtended (plist, clave ``FireWireGUID``) y luego SysInfo
    (texto, clave ``FirewireGuid``). No escribe nada.
    """
    device = _device_dir(ipod_path)
    sie = device / "SysInfoExtended"
    if sie.is_file():
        try:
            plist = plistlib.loads(sie.read_bytes())
            guid = _normalise_guid(plist.get("FireWireGUID"))
            if guid:
                return guid
        except Exception as exc:  # plist inválido: seguimos con SysInfo
            logger.debug("SysInfoExtended sin GUID legible: %s", exc)
    sysinfo = device / "SysInfo"
    if sysinfo.is_file():
        for key, value in _read_sysinfo_raw(ipod_path).items():
            if key == "FirewireGuid":
                return _normalise_guid(value)
    return None


def _read_sysinfo_raw(ipod_path: str | os.PathLike) -> dict[str, str]:
    """Pares clave:valor de SysInfo (texto), preservando valores crudos."""
    path = _device_dir(ipod_path) / "SysInfo"
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    try:
        with open(path, errors="replace") as f:
            for line in f:
                if ":" in line:
                    key, val = line.split(":", 1)
                    result[key.strip()] = val.strip()
    except Exception as exc:
        logger.warning("Lectura de SysInfo falló: %s", exc)
    return result


def _normalise_sysinfo_value(sysinfo_key: str, raw_value: object) -> str:
    val = str(raw_value).strip().rstrip("\x00")
    if sysinfo_key == "FirewireGuid":
        if val.startswith(("0x", "0X")):
            val = val[2:]
        return val.upper()
    if sysinfo_key == "ModelNumStr":
        if val.startswith("x"):
            val = "M" + val[1:]
        return val.upper().rstrip("\x00")
    if sysinfo_key == "USBProductID":
        if val.upper().startswith("0X"):
            val = val[2:]
        return val.upper().lstrip("0") or "0"
    return val


def _hash_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as exc:
        logger.warning("No se pudo hashear %s: %s", path, exc)
        return None


def _current_file_hashes(ipod_path: str | os.PathLike) -> dict[str, str]:
    device = _device_dir(ipod_path)
    hashes: dict[str, str] = {}
    for label in ("SysInfo", "SysInfoExtended"):
        h = _hash_file(device / label)
        if h is not None:
            hashes[label] = h
    return hashes


def _rank(source: str) -> int:
    return SOURCE_RANK.get(source, _WORST_RANK)


# ──────────────────────────────────────────────────────────────────────
# I/O del caché off-device
# ──────────────────────────────────────────────────────────────────────
def _read_authority_for_guid(guid: str) -> dict:
    path = _cache_dir_for_guid(guid) / AUTHORITY_FILENAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("authority.json ilegible: %s", exc)
        return {}
    if not isinstance(data, dict):
        return {}
    # Defensa ante colisión del hash de 16 chars: el GUID real vive dentro.
    if data.get("firewire_guid") and data["firewire_guid"] != guid:
        return {}
    return data


def _write_authority_for_guid(guid: str, authority: dict) -> None:
    authority["firewire_guid"] = guid
    authority["version"] = 1
    authority["last_updated"] = _now()
    directory = _cache_dir_for_guid(guid)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / AUTHORITY_FILENAME
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(authority, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, target)  # publicación atómica (fuera del iPod)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────
# Interfaz pública (misma firma que espera info.py) — path-based
# ──────────────────────────────────────────────────────────────────────
def read_authority(ipod_path: str) -> dict:
    """Lee nuestra autoridad (off-device) del dispositivo en ``ipod_path``.

    Devuelve ``{}`` si no hay caché. **Nunca** lee ni parsea el
    ``iOpenPodSysInfoAuthority`` del dispositivo: es de otro dueño y otro
    formato.
    """
    guid = _read_device_guid(ipod_path)
    if not guid:
        return {}
    return _read_authority_for_guid(guid)


def check_authority_coverage(ipod_path: str) -> tuple[bool, dict[str, str]]:
    """¿Cubre la autoridad todos los campos core? Devuelve (all_tracked, sources).

    Igual semántica que iOpenPod: si el ``SysInfo``/``SysInfoExtended`` del
    dispositivo cambió respecto a los hashes cacheados (manipulación externa),
    no se puede confiar en la procedencia → ``(False, {})``.
    """
    authority = read_authority(ipod_path)
    fields = authority.get("fields", {})
    if not isinstance(fields, dict) or not fields:
        return False, {}

    stored_hashes = authority.get("file_hashes", {})
    if not isinstance(stored_hashes, dict):
        return False, {}
    if stored_hashes:
        current = _current_file_hashes(ipod_path)
        for label, stored in stored_hashes.items():
            if stored is not None and current.get(label) != stored:
                logger.info("Autoridad: modificación externa detectada (%s).", label)
                return False, {}

    field_sources: dict[str, str] = {}
    all_tracked = True
    current_sysinfo = _read_sysinfo_raw(ipod_path)
    for sysinfo_key, device_field in SYSINFO_FIELDS:
        entry = fields.get(sysinfo_key)
        if entry is None:
            if sysinfo_key in _CORE_FIELDS:
                all_tracked = False
            continue
        if not isinstance(entry, dict):
            return False, {}
        if sysinfo_key in _CORE_FIELDS:
            current_value = current_sysinfo.get(sysinfo_key, "")
            expected_value = str(entry.get("value", "") or "")
            if not current_value or not expected_value:
                all_tracked = False
            elif _normalise_sysinfo_value(sysinfo_key, current_value) != \
                    _normalise_sysinfo_value(sysinfo_key, expected_value):
                all_tracked = False
        field_sources[device_field] = str(entry.get("source", "unknown"))
    return all_tracked, field_sources


_SENTINELS = frozenset({"", "0", "unknown", "Unknown", None})


def update_sysinfo(info: "DeviceInfo") -> None:
    """Persiste la procedencia de la identidad de ``info`` — **sin tocar el volumen**.

    A diferencia de iOpenPod, no reescribe ``SysInfo`` en el dispositivo. Solo
    fusiona la procedencia por ``SOURCE_RANK`` (se queda con la fuente más
    fiable) y refresca los hashes, todo en ``~/.cicada``.
    """
    ipod_path = getattr(info, "path", "") or ""
    if not ipod_path:
        return
    if not str(getattr(info, "model_number", "") or "").strip():
        logger.info("Salto autoridad: iPod sin identificar en %s.", ipod_path)
        return
    guid = _normalise_guid(getattr(info, "firewire_guid", "")) or _read_device_guid(ipod_path)
    if not guid:
        logger.info("Salto autoridad: sin FireWireGUID en %s.", ipod_path)
        return

    authority = _read_authority_for_guid(guid)
    fields: dict = authority.get("fields", {})
    field_sources = getattr(info, "_field_sources", {}) or {}
    now = _now()

    # Manipulación externa: si el SysInfo del dispositivo cambió, la procedencia
    # cacheada es obsoleta.
    stored_hashes = authority.get("file_hashes", {})
    current_hashes = _current_file_hashes(ipod_path)
    if stored_hashes and any(
        stored_hashes.get(k) not in (None, current_hashes.get(k))
        for k in stored_hashes
    ):
        fields = {}

    for sysinfo_key, device_field in SYSINFO_FIELDS:
        new_value = getattr(info, device_field, "")
        if new_value in _SENTINELS or not str(new_value).strip():
            continue
        new_source = str(field_sources.get(device_field, "unknown"))
        entry = fields.get(sysinfo_key)
        if entry is None:
            fields[sysinfo_key] = {"value": str(new_value), "source": new_source, "updated": now}
            continue
        # Conserva la fuente más fiable (rango menor).
        old_source = str(entry.get("source", "unknown"))
        if _rank(new_source) <= _rank(old_source):
            fields[sysinfo_key] = {"value": str(new_value), "source": new_source, "updated": now}

    authority["fields"] = fields
    authority["file_hashes"] = current_hashes
    _write_authority_for_guid(guid, authority)


def cache_sysinfo_extended(
    ipod_path: str,
    raw_xml: bytes | str,
    *,
    source: str = "unknown",
    metadata: dict | None = None,
    expected_volume_identity_key: str = "",
) -> bool:
    """Cachea un SysInfoExtended **fuera del dispositivo** y refresca hashes.

    Escribe el payload en ``~/.cicada/sysinfo/<hash>/SysInfoExtended`` y su
    registro en ``authority.json``. Nunca escribe en el volumen del iPod.
    """
    if not ipod_path or not raw_xml:
        return False
    data = _normalise_sysinfo_extended(raw_xml)
    if not data:
        return False
    guid = _read_device_guid(ipod_path)
    if not guid:
        return False
    # Rechaza cachear si el identificador de volumen esperado no coincide.
    if expected_volume_identity_key and _normalise_guid(expected_volume_identity_key) not in (None, guid):
        logger.info("SysInfoExtended no cacheado: identidad de volumen no coincide.")
        return False

    directory = _cache_dir_for_guid(guid)
    directory.mkdir(parents=True, exist_ok=True)
    payload = directory / "SysInfoExtended"
    tmp = payload.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, payload)

    authority = _read_authority_for_guid(guid)
    files = authority.setdefault("files", {})
    files["SysInfoExtended"] = {"source": source, "updated": _now(), "bytes": len(data)}
    if metadata:
        files["SysInfoExtended"]["metadata"] = {
            str(k): v for k, v in metadata.items()
            if isinstance(v, (str, int, float, bool)) and v not in ("", None)
        }
    authority["file_hashes"] = _current_file_hashes(ipod_path)
    _write_authority_for_guid(guid, authority)
    return True


def _normalise_sysinfo_extended(raw_xml: bytes | str) -> bytes:
    """Bytes canónicos del plist SysInfoExtended aptos para cachear."""
    raw = raw_xml.encode("utf-8", errors="replace") if isinstance(raw_xml, str) else bytes(raw_xml or b"")
    if not raw:
        return b""
    try:  # el parser real llega en Etapa 2b; si no está, limpieza por marcador
        from cicada.ipod.device.sysinfo import parse_sysinfo_extended  # type: ignore
        parsed = parse_sysinfo_extended(raw)
        if getattr(parsed, "plist", None) and getattr(parsed, "raw_xml", None):
            return parsed.raw_xml
    except Exception:
        pass
    for marker in (b"<?xml", b"<plist"):
        idx = raw.find(marker)
        if idx >= 0:
            raw = raw[idx:]
            break
    raw = raw.strip(b"\x00\r\n\t ")
    if raw and b"</plist>" not in raw:
        raw += b"\n</dict>\n</plist>"
    return raw


# ──────────────────────────────────────────────────────────────────────
# Limpieza del archivo de autoridad ajeno (iOpenPod) — vía write_guard
# ──────────────────────────────────────────────────────────────────────
def clean_foreign_authority(ipod_path: str) -> bool:
    """Elimina ``iOpenPodSysInfoAuthority`` del dispositivo, vía write_guard.

    Hipótesis: ese archivo (ajeno, escrito por iOpenPod en
    ``iPod_Control/Device/``) es por lo que Music.app rechaza el dispositivo.
    No es automático; se expone como ``cicada ipod clean-foreign`` para poder
    verificarlo. Devuelve ``True`` si borró algo.
    """
    from cicada.ipod.device import write_guard as wg

    mount = wg.resolve_mount(candidates=[ipod_path])
    target = mount / "iPod_Control" / "Device" / FOREIGN_AUTHORITY_FILENAME
    wg.assert_within_ipod_control(target, mount)  # confinamiento
    wg.assert_writable(mount)
    if target.is_file():
        target.unlink()
        logger.info("Eliminado %s del dispositivo.", FOREIGN_AUTHORITY_FILENAME)
        return True
    return False
