"""Control y persistencia de consentimiento para escrituras en iPod."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cicada.ipod.paths import cicada_home, guid_hash

logger = logging.getLogger(__name__)

__all__ = [
    "ConsentRecord",
    "ConsentRequiredError",
    "default_consent_dir",
    "get_consent_path",
    "has_music_app_consent",
    "get_consent_record",
    "record_music_app_consent",
    "mark_first_write_committed",
    "revoke_music_app_consent",
]

_DEFAULT_CICADA_VERSION = "0.1.0"


class ConsentRequiredError(Exception):
    pass


@dataclass(frozen=True)
class ConsentRecord:
    guid_hash: str
    music_app_ack: bool
    acked_at: str
    cicada_version: str
    first_write_committed_at: Optional[str] = None


def default_consent_dir() -> Path:
    return cicada_home() / "consent"


_guid_hash = guid_hash


def get_consent_path(guid: str | bytes, *, consent_dir: Optional[Path | str] = None) -> Path:
    base = Path(consent_dir) if consent_dir is not None else default_consent_dir()
    return base / f"{_guid_hash(guid)}.json"


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def get_consent_record(
    guid: str | bytes,
    *,
    consent_dir: Optional[Path | str] = None,
) -> Optional[ConsentRecord]:
    path = get_consent_path(guid, consent_dir=consent_dir)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ConsentRecord(
            guid_hash=raw["guid_hash"],
            music_app_ack=bool(raw["music_app_ack"]),
            acked_at=raw["acked_at"],
            cicada_version=raw.get("cicada_version", _DEFAULT_CICADA_VERSION),
            first_write_committed_at=raw.get("first_write_committed_at"),
        )
    except Exception as exc:
        logger.warning("No se pudo leer el consentimiento de %s: %s", path, exc)
        return None


def has_music_app_consent(
    guid: str | bytes,
    *,
    consent_dir: Optional[Path | str] = None,
) -> bool:
    # Comprueba si el dispositivo tiene consentimiento registrado.
    record = get_consent_record(guid, consent_dir=consent_dir)
    return bool(record and record.music_app_ack)


def record_music_app_consent(
    guid: str | bytes,
    *,
    version: str = _DEFAULT_CICADA_VERSION,
    timestamp: Optional[datetime] = None,
    consent_dir: Optional[Path | str] = None,
) -> ConsentRecord:
    # Registra el consentimiento del usuario para el dispositivo.
    dt = timestamp or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    iso_ts = dt.astimezone(timezone.utc).isoformat()

    existing = get_consent_record(guid, consent_dir=consent_dir)
    committed_at = existing.first_write_committed_at if existing else None

    record = ConsentRecord(
        guid_hash=_guid_hash(guid),
        music_app_ack=True,
        acked_at=iso_ts,
        cicada_version=version,
        first_write_committed_at=committed_at,
    )
    path = get_consent_path(guid, consent_dir=consent_dir)
    _atomic_write_json(path, asdict(record))
    return record


def mark_first_write_committed(
    guid: str | bytes,
    *,
    timestamp: Optional[datetime] = None,
    consent_dir: Optional[Path | str] = None,
) -> bool:
    record = get_consent_record(guid, consent_dir=consent_dir)
    if not record or not record.music_app_ack:
        return False

    dt = timestamp or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    iso_ts = dt.astimezone(timezone.utc).isoformat()

    updated = ConsentRecord(
        guid_hash=record.guid_hash,
        music_app_ack=record.music_app_ack,
        acked_at=record.acked_at,
        cicada_version=record.cicada_version,
        first_write_committed_at=iso_ts,
    )
    path = get_consent_path(guid, consent_dir=consent_dir)
    _atomic_write_json(path, asdict(updated))
    return True


def revoke_music_app_consent(
    guid: str | bytes,
    *,
    consent_dir: Optional[Path | str] = None,
) -> bool:
    # Revoca el consentimiento registrado para el dispositivo.
    path = get_consent_path(guid, consent_dir=consent_dir)
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False

