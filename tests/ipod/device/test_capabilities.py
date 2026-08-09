"""Tests de capabilities (vendorizado, Etapa 2a) — Nano 7G.

Verifica que la tabla estática de capacidades resuelve el Nano 7G (HASHAB,
DB comprimida + SQLite), y contrasta contra el SysInfoExtended real del fixture
las capacidades que ya conocemos (MaxTracks, PlaylistFoldersSupported…).

Nota: MaxTracks/PlaylistFoldersSupported viven en SysInfoExtended (los parsea
sysinfo.py, Etapa 2b). capabilities.py es la tabla estática de fallback. Aquí se
comprueban por separado: la tabla (family/gen) y el contenido del fixture.
"""
import plistlib
from pathlib import Path

import pytest

from cicada.ipod.device.capabilities import capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType

FIXTURE_SIE = Path(__file__).resolve().parents[2] / "fixtures" / "nano7g" / "Device" / "SysInfoExtended"

NANO7G = ("iPod Nano", "7th Gen")


def test_nano7g_resuelve_hashab():
    caps = capabilities_for_family_gen(*NANO7G)
    assert caps is not None
    assert caps.checksum is ChecksumType.HASHAB


def test_nano7g_db_format_itunescdb_comprimida_y_sqlite():
    # Arquitectura dual del Nano 7G (spec §0.1): iTunesCDB comprimido + SQLite.
    caps = capabilities_for_family_gen(*NANO7G)
    assert caps.supports_compressed_db is True   # el iTunesCDB va comprimido (zlib)
    assert caps.uses_sqlite_db is True           # + capa SQLite que lee el dispositivo


def test_nano7g_otras_capacidades_conocidas():
    caps = capabilities_for_family_gen(*NANO7G)
    assert caps.music_dirs == 20                 # F00–F49 -> 20 (según la tabla)
    assert caps.supports_video is True           # el 7G recupera vídeo
    assert caps.db_version == 0x30


def test_generacion_desconocida_devuelve_none():
    assert capabilities_for_family_gen("iPod Nano", "99th Gen") is None


@pytest.mark.skipif(not FIXTURE_SIE.exists(), reason="fixture SysInfoExtended no presente")
def test_fixture_sysinfoextended_trae_las_claves_conocidas():
    """Las capacidades que leeremos del dispositivo (Etapa 2b) están en el
    SysInfoExtended real y coinciden con lo que ya conocemos del Nano 7G."""
    data = plistlib.loads(FIXTURE_SIE.read_bytes())
    assert data["FamilyID"] == 18                       # Nano 7G
    assert data["MaxTracks"] == 65534
    assert data["PlaylistFoldersSupported"] is True
    assert data["DistinguishedSmartPlaylistsSupported"] is True
    assert data["DBVersion"] == 5
    assert data.get("FireWireGUID")                     # imprescindible para el hash
    # ModelNumStr NO viene en este dispositivo (se usa FamilyID).
    assert "ModelNumStr" not in data
