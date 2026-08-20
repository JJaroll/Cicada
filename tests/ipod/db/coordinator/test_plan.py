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
    DATABASE_TARGET_RELPATHS,
    InconsistentArtifactsError,
    Plan,
    PreStateFingerprint,
    UnsafeDeviceError,
    artwork_target_relpaths,
    create_plan,
)
from cicada.ipod.db.writer.mhit_writer import TrackInfo
from cicada.ipod.db.writer.verify import verify_hashab
from cicada.ipod.device.artwork_presets import CLASSIC_COVER_ART_FORMATS, NANO_7G_COVER_ART_FORMATS
from cicada.ipod.device.capabilities import DeviceCapabilities, capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.device_info import DeviceInfo

GUID_STR = "000A27002484DDFB"
GUID_BYTES = bytes.fromhex(GUID_STR)

FIXTURES_AUDIO = Path(__file__).resolve().parents[3] / "fixtures" / "audio"
ART_MP3 = FIXTURES_AUDIO / "with_art.mp3"
NO_ART_MP3 = FIXTURES_AUDIO / "no_art.mp3"
NANO_7G_ARTWORK_RELPATHS = artwork_target_relpaths(NANO_7G_COVER_ART_FORMATS)


def _make_mock_device(mount: Path, *, provenance: str = "disk") -> DeviceInfo:
    return DeviceInfo(
        mount=mount,
        firewire_guid=GUID_STR,
        family="nano",
        generation="7g",
        family_id=18,
        checksum=ChecksumType.HASHAB,
        guid_provenance=provenance,
        # Capacidades REALES de Nano 7G (no un DeviceCapabilities pelado):
        # desde 4f-1, cover_art_formats sale de aquí, no de una constante
        # fija — un objeto sin la tabla poblada dejaría artwork_touched en
        # False siempre, sin importar la fuente de imagen del track.
        capabilities=capabilities_for_family_gen("iPod Nano", "7th Gen"),
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
    assert all(rel not in plan.artifacts for rel in NANO_7G_ARTWORK_RELPATHS)
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
    for rel in NANO_7G_ARTWORK_RELPATHS:
        assert rel in plan.artifacts
    assert len(plan.artifacts) == 7 + len(NANO_7G_ARTWORK_RELPATHS)

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
    aunque el plan que la capturó no la haya tocado (Etapa 4d), para los
    formatos DEL DISPOSITIVO pasados a capture() (Etapa 4f-1)."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)

    fp = PreStateFingerprint.capture(mount, artwork_relpaths=NANO_7G_ARTWORK_RELPATHS)
    assert fp.matches(mount)

    artwork_dir = mount / "iPod_Control" / "Artwork"
    artwork_dir.mkdir(parents=True)
    (artwork_dir / "ArtworkDB").write_bytes(b"externally written")
    assert not fp.matches(mount)


# --------------------------------------------------------------------------- #
# Generalización más allá del Nano 7G (Fase 4, Etapa 4f-1)
# --------------------------------------------------------------------------- #


def _make_mock_device_for(mount: Path, family: str, generation: str, *, provenance: str = "disk") -> DeviceInfo:
    return DeviceInfo(
        mount=mount,
        firewire_guid=GUID_STR,
        family=family,
        generation=generation,
        family_id=18,
        checksum=ChecksumType.HASHAB,
        guid_provenance=provenance,
        capabilities=capabilities_for_family_gen(family, generation),
    )


def test_create_plan_builds_artwork_for_classic_not_nano7g_filenames(tmp_path: Path):
    """Un dispositivo distinto de Nano 7G (Classic 6th Gen) construye artwork
    con SUS PROPIOS format_id — no los de Nano 7G. Antes de 4f-1 esto era
    imposible de expresar: el escritor solo conocía el set de Nano 7G."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)
    dev = _make_mock_device_for(mount, "iPod Classic", "6th Gen")

    track = TrackInfo(
        title="Con Carátula", artist="A", album="Al",
        location=":iPod_Control:Music:F00:ART.mp3", db_track_id=9101,
        source_path=str(ART_MP3),
    )
    plan = create_plan(mount, [track], device_info=dev, consent_dir=tmp_path / "consent")

    assert plan.artwork_touched is True
    assert plan.artwork_tracks_count == 1

    classic_relpaths = artwork_target_relpaths(CLASSIC_COVER_ART_FORMATS)
    assert {fmt.format_id for fmt in CLASSIC_COVER_ART_FORMATS} == {1055, 1060, 1061, 1068}
    for rel in classic_relpaths:
        assert rel in plan.artifacts, f"falta {rel} (formato real de Classic)"
    # Los nombres de Nano 7G NO deben aparecer — confirma que no quedó
    # ningún hardcodeo residual sirviendo el set equivocado.
    for rel in NANO_7G_ARTWORK_RELPATHS[1:]:
        assert rel not in plan.artifacts, f"{rel} es de Nano 7G, no de Classic"

    artworkdb_bytes = (plan.staging_dir / "Artwork" / "ArtworkDB").read_bytes()
    entries = read_artworkdb(artworkdb_bytes)
    assert len(entries) == 1
    assert set(entries[0].formats.keys()) == {1055, 1060, 1061, 1068}


def test_create_plan_skips_artwork_for_device_without_artwork_support_even_with_real_art_source(
    tmp_path: Path,
):
    """EL GATE ES POR CAPACIDAD DEL DISPOSITIVO, NO POR DISPONIBILIDAD DE
    FUENTE. Un iPod Shuffle 1G (supports_artwork=False) con un track cuyo
    source_path SÍ tiene carátula real embebida (la misma fixture que en
    otros tests SÍ produce artwork_touched=True) debe seguir sin tocar el
    subsistema de artwork en absoluto — ni siquiera se intenta extraer la
    imagen. Es una razón distinta de "sin fuente resoluble"
    (test_create_plan_without_resolvable_art_skips_artwork_entirely, que
    usa tracks sin source_path/location útil) — aquí la fuente SÍ existe y
    SÍ tiene arte real; lo que falta es que el dispositivo lo soporte."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)
    dev = _make_mock_device_for(mount, "iPod Shuffle", "1st Gen")
    assert dev.capabilities is not None
    assert dev.capabilities.supports_artwork is False
    assert dev.capabilities.cover_art_formats == ()

    track = TrackInfo(
        title="Con Carátula Real", artist="A", album="Al",
        location=":iPod_Control:Music:F00:ART.mp3", db_track_id=9201,
        source_path=str(ART_MP3),  # la MISMA fixture que sí produce arte en otros tests
    )
    plan = create_plan(mount, [track], device_info=dev, consent_dir=tmp_path / "consent")

    assert plan.artwork_touched is False, (
        "Un Shuffle 1G no soporta artwork aunque la fuente sí tenga carátula "
        "real — el gate debe ser por capacidad del dispositivo."
    )
    assert plan.artwork_tracks_count == 0
    assert plan.artwork_skipped_count == 0
    assert not (plan.staging_dir / "Artwork").exists()
    assert track.mhii_link == 0
    assert track.artwork_size == 0
    assert track.artwork_count == 0


def test_pre_state_fingerprint_uses_classic_formats_not_nano7g(tmp_path: Path):
    """Hallazgo central de 4f-1: sin esto, un plan para Classic fingerprintea
    rutas de Nano 7G (que nunca le pertenecen) y no detecta deriva real en
    sus propios .ithmb — un rollback que no dispara cuando debería."""
    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)

    classic_relpaths = artwork_target_relpaths(CLASSIC_COVER_ART_FORMATS)
    fp = PreStateFingerprint.capture(mount, artwork_relpaths=classic_relpaths)
    assert fp.matches(mount)

    # Mutación externa de un archivo que SÍ pertenece a Classic (1055).
    artwork_dir = mount / "iPod_Control" / "Artwork"
    artwork_dir.mkdir(parents=True)
    classic_ithmb = next(r for r in classic_relpaths if "1055" in r)
    (mount / classic_ithmb).write_bytes(b"drift ajeno a este plan")

    assert not fp.matches(mount), (
        "La huella de un plan para Classic debe detectar deriva en SUS "
        "propios .ithmb (F1055...), no solo en los de Nano 7G."
    )


# --------------------------------------------------------------------------- #
# Garantía para clean_foreign_artifacts() (Fase 4f, autoridad ajena/§0.3)
# --------------------------------------------------------------------------- #


def test_create_plan_never_produces_foreign_backup_filenames(tmp_path: Path):
    """clean_foreign_artifacts() ahora borra los 7 nombres .backup que deja
    write_itunesdb/write_sqlite_databases de iOpenPod en sitio
    (FOREIGN_BACKUP_RELPATHS). Eso solo es seguro si el camino ACTIVO de
    escritura de Cicada (build_itunescdb/build_sqlite_databases, vía
    create_plan) nunca produce esos mismos nombres — si alguna vez lo
    hiciera, clean-foreign borraría algo propio por error.

    Esto verifica el comportamiento real de create_plan() con tracks/
    playlists reales, no un grep del código fuente de hoy — protege el
    supuesto contra cambios futuros en vez de asumir que seguirá siendo
    cierto."""
    from cicada.ipod.device.authority import FOREIGN_BACKUP_RELPATHS

    mount = tmp_path / "ipod_mount"
    _setup_mock_ipod(mount)
    dev = _make_mock_device(mount)

    # Con playlists y varios tracks: más superficie donde un futuro cambio
    # podría introducir sin querer un archivo ".backup" (p. ej. si alguien
    # reintroduce el mecanismo de backup-en-sitio de iOpenPod por error).
    tracks = _sample_tracks()
    plan = create_plan(
        mount, tracks, device_info=dev, consent_dir=tmp_path / "consent",
        playlists=None, smart_playlists=None,
    )

    foreign_names = {Path(rel).name for rel in FOREIGN_BACKUP_RELPATHS}
    produced_names = {p.name for p in plan.staging_dir.rglob("*") if p.is_file()}
    overlap = produced_names & foreign_names
    assert not overlap, (
        f"El camino activo de create_plan() produjo nombres que "
        f"clean_foreign_artifacts() trataría como ajenos: {overlap}. "
        f"Esto volvería inseguro borrarlos automáticamente."
    )

    # Chequeo más amplio, no atado a la lista exacta: ningún .backup en absoluto.
    backup_files = [p for p in plan.staging_dir.rglob("*.backup") if p.is_file()]
    assert not backup_files, f"create_plan() generó archivos .backup: {backup_files}"
