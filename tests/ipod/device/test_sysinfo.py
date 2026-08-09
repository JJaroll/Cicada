"""Tests de sysinfo (vendorizado, Etapa 2b) — parseo puro, sin hardware.

Test obligatorio contra el fixture real: parsear el SysInfoExtended del Nano 7G
y extraer FireWireGUID, FamilyID, MaxTracks y DBVersion con los valores que ya
conocemos. Más cascada plist→regex, texto SysInfo, y normalize_guid.
"""
from pathlib import Path

import pytest

from cicada.ipod.device.sysinfo import (
    normalize_guid,
    parse_sysinfo_extended,
    parse_sysinfo_text,
)

FIXTURE_SIE = Path(__file__).resolve().parents[2] / "fixtures" / "nano7g" / "Device" / "SysInfoExtended"

# Valores conocidos del dispositivo real.
GUID = "000A27002484DDFB"


# --------------------------------------------------------------------------- #
# OBLIGATORIO: fixture real
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not FIXTURE_SIE.exists(), reason="fixture SysInfoExtended no presente")
def test_fixture_extrae_valores_conocidos():
    parsed = parse_sysinfo_extended(FIXTURE_SIE.read_bytes())
    assert parsed.used_regex_fallback is False   # XML válido: plist directo

    # Vía plist crudo.
    assert parsed.plist["FamilyID"] == 18
    assert parsed.plist["MaxTracks"] == 65534
    assert parsed.plist["DBVersion"] == 5
    assert normalize_guid(parsed.plist["FireWireGUID"]) == GUID

    # Vía identidad normalizada (lo que consume el scanner/DeviceInfo).
    ident = parsed.identity
    assert ident["firewire_guid"] == GUID
    assert ident["family_id"] == 18
    assert ident["db_version"] == 5
    assert ident["max_tracks"] == 65534


@pytest.mark.skipif(not FIXTURE_SIE.exists(), reason="fixture SysInfoExtended no presente")
def test_fixture_sin_modelnumstr_no_rompe():
    # El Nano 7G no trae ModelNumStr: la identidad se resuelve sin él, por FamilyID.
    ident = parse_sysinfo_extended(FIXTURE_SIE.read_bytes()).identity
    assert "model_number" not in ident
    assert ident["family_id"] == 18
    assert ident["firewire_guid"] == GUID


# --------------------------------------------------------------------------- #
# Cascada de formatos: plist válido / truncado / con basura SCSI / regex
# --------------------------------------------------------------------------- #
_XML = (
    b"<?xml version='1.0'?>\n<plist version='1.0'><dict>"
    b"<key>FamilyID</key><integer>18</integer>"
    b"<key>FireWireGUID</key><string>000A27002484DDFB</string>"
    b"</dict></plist>"
)


def test_plist_valido_sin_fallback():
    p = parse_sysinfo_extended(_XML)
    assert p.used_regex_fallback is False
    assert p.plist["FamilyID"] == 18


def test_plist_truncado_se_repara():
    # Sin </plist>: parse_sysinfo_extended añade cierre y reintenta.
    truncado = _XML.replace(b"</dict></plist>", b"")
    p = parse_sysinfo_extended(truncado)
    assert p.plist.get("FamilyID") == 18


def test_basura_scsi_al_inicio_y_nulos_al_final():
    # Payloads de SCSI/USB traen bytes antes del XML y padding \x00 al final.
    sucio = b"\x00\x00SCSIVPD-JUNK" + _XML + b"\x00\x00\x00"
    p = parse_sysinfo_extended(sucio)
    assert p.plist["FamilyID"] == 18
    assert normalize_guid(p.plist["FireWireGUID"]) == GUID


def test_fallback_regex_cuando_plist_falla():
    # Sin marcador <?xml/<plist parseable, pero con pares key/valor: regex.
    blob = (
        b"SCSIVPD\x00<key>FamilyID</key><integer>18</integer>"
        b"<key>DBVersion</key><integer>5</integer>"
    )
    p = parse_sysinfo_extended(blob)
    assert p.used_regex_fallback is True
    assert p.plist["FamilyID"] == 18
    assert p.plist["DBVersion"] == 5


# --------------------------------------------------------------------------- #
# SysInfo (texto plano)
# --------------------------------------------------------------------------- #
def test_parse_sysinfo_text():
    d = parse_sysinfo_text("FirewireGuid: 0x000A27002484DDFB\nModelNumStr: \n")
    assert d["FirewireGuid"] == "0x000A27002484DDFB"
    assert d["ModelNumStr"] == ""


# --------------------------------------------------------------------------- #
# normalize_guid
# --------------------------------------------------------------------------- #
def test_normalize_guid_variantes():
    assert normalize_guid("0x000a27002484ddfb") == GUID   # prefijo 0x + minúsculas
    assert normalize_guid("000A 2700 2484 DDFB") == GUID  # con espacios
    assert normalize_guid(GUID) == GUID


def test_normalize_guid_invalidos():
    assert normalize_guid(None) == ""
    assert normalize_guid("") == ""
    assert normalize_guid("0000000000000000") == ""       # todo ceros
    assert normalize_guid("nothexvalue!!!!") == ""        # no es hex
