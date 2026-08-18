"""Tests unitarios para el generador de planes (plan.py) — Etapa 2c."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

wasmtime = pytest.importorskip("wasmtime", reason="wasmtime no instalado")

from cicada.ipod.db.artwork.chunks import read_artworkdb
from cicada.ipod.db.coordinator.consent import record_music_app_consent
from cicada.ipod.db.coordinator.plan import (
    ARTWORK_TARGET_RELPATHS,
    DATABASE_TARGET_RELPATHS,
    InconsistentArtifactsError,
    Plan,
    PreStateFingerprint,
    UnsafeDeviceError,
    create_plan,
)
from cicada.ipod.db.writer.mhit_writer import TrackInfo
from cicada.ipod.db.writer.verify import verify_hashab
from cicada.ipod.device.capabilities import DeviceCapabilities
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.device_info import DeviceInfo

GUID_STR = "000A27002484DDFB"
GUID_BYTES = bytes.fromhex(GUID_STR)

FIXTURES_AUDIO = Path(__file__).resolve().parents[3] / "fixtures" / "audio"
ART_MP3 = FIXTURES_AUDIO / "with_art.mp3"
NO_ART_MP3 = FIXTURES_AUDIO / "no_art.mp3"


def _make_mock_device(mount: Path, *, provenance: str = "disk") -> DeviceInfo:
    return DeviceInfo(
        mount=mount,
        firewire_guid=GUID_STR,
        family="nano",
        generation="7g",
        family_id=18,
        checksum=ChecksumType.HASHAB,
        guid_provenance=provenance,
        capabilities=DeviceCapabilities(checksum=ChecksumType.HASHAB),
    )


def _sample_tracks() -> list[TrackInfo]:
    return [
        TrackInfo(
            title="Track 1",
            artist="Artist 1",
            album="Album 1",
            location=":iPod_Control:Music:F00:ABCD.mp3",
            db_track_id=1001,
        ),
        TrackInfo(
            title="Track 2",
            artist="Artist 2",
            album="Album 2",
            location=":iPod_Control:Music:F01:EFGH.mp3",
            db_track_id=1002,
        ),
    ]


def _setup_mock_ipod(mount: Path) -> None:
    itunes = mount / "iPod_Control" / "iTunes"
    itlp = itunes / "iTunes Library.itlp"
    itlp.mkdir(parents=True, exist_ok=True)
    (itunes / "iTunesCDB").write_bytes(b"dummy cdb content")
    for fn in ("Library.itdb", "Locations.itdb", "Locations.itdb.cbk", "Dynamic.itdb", "Extras.itdb", "Genius.itdb"):
        (itlp / fn).write_bytes(f"dummy {fn}".encode("utf-8"))


def test_create_plan_success(tmp_path: Path):
    """Crea un plan correctamente en staging y calcula huellas y metadatos."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)
    dev = _make_mock_device(mount, provenance="disk")

    tracks = _sample_tracks()
    plan = create_plan(
        mount,
        tracks,
        device_info=dev,
        consent_dir=tmp_path / "consent",
    )

    assert isinstance(plan, Plan)
    assert plan.guid == GUID_STR
    assert plan.firewire_id == GUID_BYTES
    assert plan.checksum_type is ChecksumType.HASHAB
    assert plan.tracks_count == 2
    assert plan.write_safe is True
    assert plan.consent_needed is True  # No consent yet

    # Staging artifacts existen y están poblados
    assert plan.staging_dir.is_dir()
    assert (plan.staging_dir / "iTunesCDB").is_file()
    assert (plan.staging_dir / "iTunes Library.itlp" / "Library.itdb").is_file()

    # PreStateFingerprint coincide con el estado inicial
    assert plan.pre_state.matches(mount)

    # 7 artefactos registrados en metadatos
    assert len(plan.artifacts) == 7
    for rel in DATABASE_TARGET_RELPATHS:
        assert rel in plan.artifacts
        size, sha256_hash = plan.artifacts[rel]
        assert size > 0
        assert len(sha256_hash) == 64


def test_create_plan_rejects_unsafe_guid(tmp_path: Path):
    """Rechaza dispositivos con procedencia de GUID insegura (ej: cache_weak)."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)
    dev = _make_mock_device(mount, provenance="cache_weak")

    with pytest.raises(UnsafeDeviceError) as exc_info:
        create_plan(mount, _sample_tracks(), device_info=dev)
    assert "cache_weak" in str(exc_info.value)


def test_create_plan_consent_already_granted(tmp_path: Path):
    """Si ya existe consentimiento, plan.consent_needed es False."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)
    dev = _make_mock_device(mount, provenance="disk")
    consent_dir = tmp_path / "consent"

    record_music_app_consent(GUID_STR, consent_dir=consent_dir)

    plan = create_plan(
        mount,
        _sample_tracks(),
        device_info=dev,
        consent_dir=consent_dir,
    )
    assert plan.consent_needed is False


def test_pre_state_fingerprint_matching_and_drift(tmp_path: Path):
    """PreStateFingerprint detecta cualquier mutación en los archivos existentes."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)

    fp = PreStateFingerprint.capture(mount)
    assert fp.matches(mount)

    # Mutar un archivo en el iPod
    (mount / "iPod_Control" / "iTunes" / "iTunesCDB").write_bytes(b"modified content")
    assert not fp.matches(mount)


def test_staging_artifacts_validity(tmp_path: Path):
    """Los artefactos en staging pasan verify_hashab y son bases SQLite legibles."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)
    dev = _make_mock_device(mount, provenance="usb")

    plan = create_plan(
        mount,
        _sample_tracks(),
        device_info=dev,
        consent_dir=tmp_path / "consent",
    )

    # Verificar HASHAB en el iTunesCDB de staging
    cdb_bytes = (plan.staging_dir / "iTunesCDB").read_bytes()
    assert verify_hashab(cdb_bytes, GUID_BYTES)

    # Verificar lectura de cada .itdb con sqlite3
    itlp_dir = plan.staging_dir / "iTunes Library.itlp"
    for fn in ("Library.itdb", "Locations.itdb", "Dynamic.itdb", "Extras.itdb", "Genius.itdb"):
        db_file = itlp_dir / fn
        con = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
        res = con.execute("PRAGMA integrity_check").fetchone()
        assert res[0] == "ok"
        con.close()


def test_custom_staging_base(tmp_path: Path):
    """Permite indicar una ruta base personalizada para el staging."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)
    dev = _make_mock_device(mount)

    custom_staging = tmp_path / "custom_staging"
    plan = create_plan(
        mount,
        _sample_tracks(),
        device_info=dev,
        staging_base=custom_staging,
        consent_dir=tmp_path / "consent",
    )

    assert custom_staging in plan.staging_dir.parents
    assert (plan.staging_dir / "iTunesCDB").is_file()


# --------------------------------------------------------------------------- #
# Artwork (Fase 4, Etapa 4d)
# --------------------------------------------------------------------------- #


def test_create_plan_without_resolvable_art_skips_artwork_entirely(tmp_path: Path):
    """Sin fuente de imagen resoluble (caso de todos los tests anteriores),
    el subsistema de artwork no se toca: ni staging, ni artefactos, ni campos."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)
    dev = _make_mock_device(mount)

    plan = create_plan(mount, _sample_tracks(), device_info=dev, consent_dir=tmp_path / "consent")

    assert plan.artwork_touched is False
    assert plan.artwork_tracks_count == 0
    assert not (plan.staging_dir / "Artwork").exists()
    assert all(rel not in plan.artifacts for rel in ARTWORK_TARGET_RELPATHS)
    assert len(plan.artifacts) == 7
    for t in plan.tracks:
        assert t.mhii_link == 0
        assert t.artwork_size == 0
        assert t.artwork_count == 0


def test_create_plan_builds_artwork_from_source_path(tmp_path: Path):
    """Un track con source_path a un archivo con carátula embebida obtiene
    mhii_link/artwork_size/artwork_count, y ArtworkDB se stagea y verifica."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)
    dev = _make_mock_device(mount)

    track = TrackInfo(
        title="Con Carátula",
        artist="Artista",
        album="Álbum",
        location=":iPod_Control:Music:F00:ART.mp3",
        db_track_id=3001,
        source_path=str(ART_MP3),
    )

    plan = create_plan(mount, [track], device_info=dev, consent_dir=tmp_path / "consent")

    assert plan.artwork_touched is True
    assert plan.artwork_tracks_count == 1
    assert plan.artwork_skipped_count == 0
    assert track.mhii_link != 0
    from cicada.shared.artwork import extract_embedded_artwork
    expected_art_bytes, _mime = extract_embedded_artwork(ART_MP3)
    assert track.artwork_size == len(expected_art_bytes)
    assert track.artwork_count == 1

    # Artefactos de staging: ArtworkDB + 4 .ithmb, todos registrados.
    for rel in ARTWORK_TARGET_RELPATHS:
        assert rel in plan.artifacts
    assert len(plan.artifacts) == 7 + len(ARTWORK_TARGET_RELPATHS)

    artworkdb_bytes = (plan.staging_dir / "Artwork" / "ArtworkDB").read_bytes()
    entries = read_artworkdb(artworkdb_bytes)
    assert len(entries) == 1
    assert entries[0].db_track_id == 3001
    assert entries[0].img_id == track.mhii_link


def test_create_plan_falls_back_to_on_device_location_for_artwork(tmp_path: Path):
    """Track SIN source_path (round-trip de una pista ya existente, como al
    recargar la biblioteca vía load_ipod_library) resuelve su carátula desde
    el propio audio en el iPod usando `location` — mismo patrón que
    _heal_track_lengths en coordinator/media.py. Este es el fix al bug de
    regresión encontrado antes de implementar 4d."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)
    dev = _make_mock_device(mount)

    on_device_audio = mount / "iPod_Control" / "Music" / "F00" / "EXIST.mp3"
    on_device_audio.parent.mkdir(parents=True, exist_ok=True)
    on_device_audio.write_bytes(ART_MP3.read_bytes())

    track = TrackInfo(
        title="Ya en el iPod",
        artist="Artista",
        album="Álbum",
        location=":iPod_Control:Music:F00:EXIST.mp3",
        db_track_id=3002,
        # source_path=None a propósito: simula un track recargado, no nuevo.
    )

    plan = create_plan(mount, [track], device_info=dev, consent_dir=tmp_path / "consent")

    assert plan.artwork_touched is True
    assert plan.artwork_tracks_count == 1
    assert track.mhii_link != 0


def test_create_plan_no_art_track_gets_zero_fields_when_others_have_art(tmp_path: Path):
    """En un plan con artwork_touched=True, un track SIN carátula queda en
    mhii_link=0 explícito (no en algún valor residual)."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)
    dev = _make_mock_device(mount)

    with_art = TrackInfo(
        title="Con arte", artist="A", album="Al",
        location=":iPod_Control:Music:F00:A.mp3", db_track_id=4001,
        source_path=str(ART_MP3),
    )
    without_art = TrackInfo(
        title="Sin arte", artist="B", album="Bl",
        location=":iPod_Control:Music:F01:B.mp3", db_track_id=4002,
        source_path=str(NO_ART_MP3),
    )

    plan = create_plan(mount, [with_art, without_art], device_info=dev, consent_dir=tmp_path / "consent")

    assert plan.artwork_touched is True
    assert plan.artwork_tracks_count == 1
    assert with_art.mhii_link != 0
    assert without_art.mhii_link == 0
    assert without_art.artwork_size == 0
    assert without_art.artwork_count == 0


def test_pre_state_fingerprint_covers_artwork_paths(tmp_path: Path):
    """PreStateFingerprint detecta deriva también en iPod_Control/Artwork/,
    aunque el plan que la capturó no la haya tocado (Etapa 4d)."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)

    fp = PreStateFingerprint.capture(mount)
    assert fp.matches(mount)

    artwork_dir = mount / "iPod_Control" / "Artwork"
    artwork_dir.mkdir(parents=True)
    (artwork_dir / "ArtworkDB").write_bytes(b"externally written")
    assert not fp.matches(mount)
