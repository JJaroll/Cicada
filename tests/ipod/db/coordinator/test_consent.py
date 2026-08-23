"""Tests unitarios para el gate de consentimiento de Music.app (consent.py)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cicada.ipod.db.coordinator.consent import (
    ConsentRecord,
    ConsentRequiredError,
    get_consent_path,
    get_consent_record,
    has_music_app_consent,
    mark_first_write_committed,
    record_music_app_consent,
    revoke_music_app_consent,
)

GUID_A = "000A27002484DDFB"
GUID_B = "000A270011223344"
GUID_A_BYTES = bytes.fromhex(GUID_A)


def test_no_consent_by_default(tmp_path: Path):
    """Un dispositivo no registrado no tiene consentimiento."""
    assert not has_music_app_consent(GUID_A, consent_dir=tmp_path)
    assert get_consent_record(GUID_A, consent_dir=tmp_path) is None


def test_record_and_read_consent(tmp_path: Path):
    """Registrar consentimiento crea el JSON y permite recuperarlo."""
    ts = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)
    rec = record_music_app_consent(
        GUID_A,
        version="0.2.0",
        timestamp=ts,
        consent_dir=tmp_path,
    )
    assert rec.music_app_ack is True
    assert rec.cicada_version == "0.2.0"
    assert rec.acked_at == "2026-08-14T12:00:00+00:00"
    assert rec.first_write_committed_at is None

    assert has_music_app_consent(GUID_A, consent_dir=tmp_path)
    read_rec = get_consent_record(GUID_A, consent_dir=tmp_path)
    assert read_rec == rec


def test_guid_tolerance_str_and_bytes(tmp_path: Path):
    """Tolerancia a formato string (mayús/minús/espacios) y bytes binarios."""
    record_music_app_consent(GUID_A_BYTES, consent_dir=tmp_path)
    assert has_music_app_consent(GUID_A, consent_dir=tmp_path)
    assert has_music_app_consent(GUID_A.lower(), consent_dir=tmp_path)
    assert has_music_app_consent(f"  {GUID_A}  ", consent_dir=tmp_path)
    assert has_music_app_consent(GUID_A_BYTES, consent_dir=tmp_path)


def test_guid_isolation(tmp_path: Path):
    """El consentimiento para GUID_A no otorga consentimiento para GUID_B."""
    record_music_app_consent(GUID_A, consent_dir=tmp_path)
    assert has_music_app_consent(GUID_A, consent_dir=tmp_path)
    assert not has_music_app_consent(GUID_B, consent_dir=tmp_path)


def test_mark_first_write_committed(tmp_path: Path):
    """Marcar primera escritura exitosa actualiza first_write_committed_at."""
    assert not mark_first_write_committed(GUID_A, consent_dir=tmp_path)

    record_music_app_consent(GUID_A, consent_dir=tmp_path)
    ts_commit = datetime(2026, 8, 14, 12, 5, 0, tzinfo=timezone.utc)
    ok = mark_first_write_committed(GUID_A, timestamp=ts_commit, consent_dir=tmp_path)
    assert ok is True

    rec = get_consent_record(GUID_A, consent_dir=tmp_path)
    assert rec is not None
    assert rec.first_write_committed_at == "2026-08-14T12:05:00+00:00"
    assert rec.music_app_ack is True


def test_corrupt_or_empty_json_handling(tmp_path: Path):
    """JSON corrupto degrada a None / False sin lanzar excepciones no controladas."""
    path = get_consent_path(GUID_A, consent_dir=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text("", encoding="utf-8")
    assert not has_music_app_consent(GUID_A, consent_dir=tmp_path)
    assert get_consent_record(GUID_A, consent_dir=tmp_path) is None

    path.write_text("{corrupt: true", encoding="utf-8")
    assert not has_music_app_consent(GUID_A, consent_dir=tmp_path)
    assert get_consent_record(GUID_A, consent_dir=tmp_path) is None


def test_atomic_write_no_leftover_temps(tmp_path: Path):
    """La escritura atómica no deja archivos temporales residuales."""
    record_music_app_consent(GUID_A, consent_dir=tmp_path)
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".json"
    assert ".tmp" not in files[0].name


def test_revoke_consent(tmp_path: Path):
    """Revocar consentimiento borra el archivo y revierte el estado a False."""
    record_music_app_consent(GUID_A, consent_dir=tmp_path)
    assert has_music_app_consent(GUID_A, consent_dir=tmp_path)

    assert revoke_music_app_consent(GUID_A, consent_dir=tmp_path)
    assert not has_music_app_consent(GUID_A, consent_dir=tmp_path)

    assert revoke_music_app_consent(GUID_A, consent_dir=tmp_path)
