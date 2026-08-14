"""Generador de planes de escritura en staging off-device (dry-run) — Etapa 2c.

Un :class:`Plan` representa una mutación propuesta para la biblioteca del iPod:
1. Valida precondiciones de seguridad (GUID write-safe).
2. Determina si se requiere advertencia previa de Music.app.
3. Captura una huella criptográfica del estado pre-existente (:class:`PreStateFingerprint`)
   para que :func:`apply` pueda detectar si el plan quedó obsoleto antes de escribir.
4. Genera los 7 artefactos de la base de datos en un directorio de staging **off-device**:
   - `iTunesCDB` (comprimido y firmado).
   - `Library.itdb`, `Locations.itdb`, `Dynamic.itdb`, `Extras.itdb`, `Genius.itdb`, `Locations.itdb.cbk`.
5. Ejecuta verificaciones internas de consistencia sobre los artefactos en staging antes de congelar el plan.

Este módulo **NUNCA** escribe en el volumen del iPod.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cicada.ipod.db.coordinator.consent import (
    _guid_hash,
    has_music_app_consent,
)
from cicada.ipod.db.shared.device_time import DeviceTimeContext
from cicada.ipod.db.sqlite.build import ITLP_FILES, build_sqlite_databases
from cicada.ipod.db.writer.build import build_itunescdb
from cicada.ipod.db.writer.mhit_writer import TrackInfo
from cicada.ipod.db.writer.mhyp_writer import PlaylistInfo
from cicada.ipod.db.writer.verify import verify_hashab
from cicada.ipod.device.capabilities import DeviceCapabilities, capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.device_info import DeviceInfo

__all__ = [
    "DATABASE_TARGET_RELPATHS",
    "PreStateFingerprint",
    "Plan",
    "PlanError",
    "UnsafeDeviceError",
    "InconsistentArtifactsError",
    "create_plan",
]

#: Las 7 rutas relativas canónicas en el iPod que componen la base de datos completa.
DATABASE_TARGET_RELPATHS: tuple[str, ...] = (
    "iPod_Control/iTunes/iTunesCDB",
    "iPod_Control/iTunes/iTunes Library.itlp/Library.itdb",
    "iPod_Control/iTunes/iTunes Library.itlp/Locations.itdb",
    "iPod_Control/iTunes/iTunes Library.itlp/Locations.itdb.cbk",
    "iPod_Control/iTunes/iTunes Library.itlp/Dynamic.itdb",
    "iPod_Control/iTunes/iTunes Library.itlp/Extras.itdb",
    "iPod_Control/iTunes/iTunes Library.itlp/Genius.itdb",
)


class PlanError(Exception):
    """Base de los errores durante la generación del plan."""


class UnsafeDeviceError(PlanError):
    """El dispositivo no cuenta con una procedencia de GUID segura para escritura."""


class InconsistentArtifactsError(PlanError):
    """Los artefactos generados en staging no superaron la verificación de autoconsistencia."""


def _hash_file(path: Path) -> Optional[tuple[int, str]]:
    """Calcula (size, sha256) de un archivo si existe, o None."""
    if not path.is_file():
        return None
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
            size += len(chunk)
    return (size, h.hexdigest())


@dataclass(frozen=True)
class PreStateFingerprint:
    """Huella criptográfica de los archivos de base de datos actuales en el iPod."""

    files: dict[str, Optional[tuple[int, str]]]  # relpath -> (size_bytes, sha256) o None

    @classmethod
    def capture(cls, mount: Path | str) -> PreStateFingerprint:
        """Captura los hashes y tamaños de los 7 archivos de base de datos en mount."""
        mount_path = Path(mount)
        fingerprint = {}
        for rel in DATABASE_TARGET_RELPATHS:
            full = mount_path / rel
            fingerprint[rel] = _hash_file(full)
        return cls(files=fingerprint)

    def matches(self, mount: Path | str) -> bool:
        """Comprueba si el estado actual del disco coincide exactamente con esta huella."""
        current = PreStateFingerprint.capture(mount)
        return self.files == current.files


@dataclass(frozen=True)
class Plan:
    """Plan de escritura congelado listo para ser ejecutado por apply()."""

    guid: str
    firewire_id: bytes
    checksum_type: ChecksumType
    staging_dir: Path
    tracks: list[TrackInfo]
    pre_state: PreStateFingerprint
    consent_needed: bool
    write_safe: bool
    created_at: str
    capabilities: Optional[DeviceCapabilities] = None
    time_context: Optional[DeviceTimeContext] = None
    artifacts: dict[str, tuple[int, str]] = field(default_factory=dict)
    _temp_dir_handle: Optional[object] = field(default=None, repr=False, compare=False)

    @property
    def tracks_count(self) -> int:
        return len(self.tracks)


def create_plan(
    mount: str | Path,
    tracks: list[TrackInfo],
    *,
    device_info: DeviceInfo,
    playlists: Optional[list[PlaylistInfo]] = None,
    smart_playlists: Optional[list[PlaylistInfo]] = None,
    master_playlist_name: str = "iPod",
    time_context: Optional[DeviceTimeContext] = None,
    staging_base: Optional[str | Path] = None,
    consent_dir: Optional[str | Path] = None,
    timestamp: Optional[datetime] = None,
) -> Plan:
    """Construye un plan de escritura dry-run completo en staging off-device.

    :raises UnsafeDeviceError: si el GUID del dispositivo proviene de una fuente débil.
    :raises InconsistentArtifactsError: si los artefactos en staging fallan la verificación.
    """
    # 1. Gate de seguridad del dispositivo
    if not device_info.guid_is_write_safe or not device_info.firewire_guid:
        raise UnsafeDeviceError(
            f"El dispositivo en {mount} no tiene un GUID de procedencia segura para escribir "
            f"(provenance={device_info.guid_provenance!r}). Se requiere disk, cache_strong o usb."
        )

    guid_str = device_info.firewire_guid
    firewire_id = bytes.fromhex(guid_str)
    checksum_type = device_info.checksum or ChecksumType.HASHAB

    caps = device_info.capabilities
    if caps is None and device_info.family and device_info.generation:
        caps = capabilities_for_family_gen(
            device_info.family,
            device_info.generation,
            capacity=device_info.capacity,
            model_number=device_info.model_number,
        )
    if caps is None:
        caps = capabilities_for_family_gen("iPod Nano", "7th Gen")

    # 2. Gate de consentimiento de Music.app
    consent_needed = not has_music_app_consent(guid_str, consent_dir=consent_dir)

    # 3. Huella del estado actual
    pre_state = PreStateFingerprint.capture(mount)

    # 4. Directorio de staging off-device
    temp_handle = None
    if staging_base is not None:
        base = Path(staging_base)
        base.mkdir(parents=True, exist_ok=True)
        ts_tag = int((timestamp or datetime.now(timezone.utc)).timestamp())
        staging_dir = base / f"plan-{_guid_hash(guid_str)[:8]}-{ts_tag}"
        staging_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_handle = tempfile.TemporaryDirectory(prefix="cicada-plan-")
        staging_dir = Path(temp_handle.name)

    # 5. Generación de artefactos en staging
    cdb_path = staging_dir / "iTunesCDB"
    itlp_dir = staging_dir / "iTunes Library.itlp"

    # 5a. iTunesCDB
    cdb_bytes = build_itunescdb(
        tracks,
        firewire_id=firewire_id,
        checksum=checksum_type,
        capabilities=caps,
        playlists_type2=playlists,
        playlists_type5=smart_playlists,
        master_playlist_name=master_playlist_name,
        time_context=time_context,
    )
    cdb_path.write_bytes(cdb_bytes)

    # 5b. SQLite .itdb + .cbk
    build_sqlite_databases(
        itlp_dir,
        tracks,
        firewire_id=firewire_id,
        checksum=checksum_type,
        capabilities=caps,
        playlists=playlists,
        smart_playlists=smart_playlists,
        master_playlist_name=master_playlist_name,
        time_context=time_context,
    )

    # 6. Verificación interna de los artefactos generados
    if checksum_type is ChecksumType.HASHAB:
        if not verify_hashab(cdb_bytes, firewire_id):
            raise InconsistentArtifactsError(
                "El iTunesCDB generado en staging no superó verify_hashab."
            )

    for fn in ITLP_FILES:
        target_file = itlp_dir / fn
        if not target_file.is_file() or target_file.stat().st_size == 0:
            raise InconsistentArtifactsError(
                f"Falta el archivo requerido {fn} en el staging de iTunes Library.itlp."
            )
        # Validación de lectura SQLite para los .itdb
        if fn.endswith(".itdb"):
            try:
                con = sqlite3.connect(f"file:{target_file}?mode=ro", uri=True)
                con.execute("PRAGMA schema_version").fetchone()
                con.close()
            except Exception as exc:
                raise InconsistentArtifactsError(
                    f"La base SQLite generada {fn} es ilegible: {exc}"
                ) from exc

    # 7. Recolección de metadatos de los artefactos
    artifacts: dict[str, tuple[int, str]] = {}
    cdb_info = _hash_file(cdb_path)
    assert cdb_info is not None
    artifacts["iPod_Control/iTunes/iTunesCDB"] = cdb_info

    for fn in ITLP_FILES:
        info = _hash_file(itlp_dir / fn)
        assert info is not None
        artifacts[f"iPod_Control/iTunes/iTunes Library.itlp/{fn}"] = info

    dt = timestamp or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    created_at = dt.astimezone(timezone.utc).isoformat()

    return Plan(
        guid=guid_str,
        firewire_id=firewire_id,
        checksum_type=checksum_type,
        staging_dir=staging_dir,
        tracks=tracks,
        pre_state=pre_state,
        consent_needed=consent_needed,
        write_safe=True,
        created_at=created_at,
        capabilities=caps,
        time_context=time_context,
        artifacts=artifacts,
        _temp_dir_handle=temp_handle,
    )
