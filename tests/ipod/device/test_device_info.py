"""Tests de device_info + family_ids (Etapa 2c) — identidad solo del volumen.

Contra el fixture nano7g, sin dispositivo conectado. Verifica: identificación,
validación cruzada de las dos vías (family_id vs serial), no-escritura, USB
opcional, y degradación a parcial sin excepción.
"""
import plistlib
from pathlib import Path

import pytest

from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.device_info import (
    DeviceInfo,
    identification_methods,
    read_device_info,
)
from cicada.ipod.device.family_ids import FAMILY_IDS, lookup_family_id

import sys

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "nano7g-iopenpod"
HAS_FIXTURE = (FIXTURE / "Device" / "SysInfoExtended").exists()
skip_no_fixture = pytest.mark.skipif(
    not HAS_FIXTURE or sys.platform == "win32",
    reason="fixture nano7g no presente (o symlinks no POSIX)",
)


@pytest.fixture
def mount(tmp_path):
    """Mount con iPod_Control apuntando al contenido del fixture."""
    m = tmp_path / "IPOD"
    m.mkdir()
    (m / "iPod_Control").symlink_to(FIXTURE)
    return m


def test_tabla_solo_el_18_verificado():
    assert set(FAMILY_IDS) == {18}
    e = FAMILY_IDS[18]
    assert (e.family, e.generation) == ("iPod Nano", "7th Gen")
    assert e.verified is True


def test_source_sin_datos_sensibles():
    src = FAMILY_IDS[18].source
    assert "DCYM" not in src and "000A2700" not in src
    assert "MD476" in src


def test_lookup_family_id_desconocido_none():
    assert lookup_family_id(9999) is None
    assert lookup_family_id(None) is None


@skip_no_fixture
def test_identifica_nano7g_por_family_id(mount):
    info = read_device_info(mount)
    assert info.family == "iPod Nano"
    assert info.generation == "7th Gen"
    assert info.checksum is ChecksumType.HASHAB
    assert info.identified_by == "family_id"
    assert info.partial is False
    assert info.family_id == 18
    assert info.capabilities is not None
    assert info.capacity == "16GB"


@skip_no_fixture
def test_validacion_cruzada_family_id_vs_serial():
    data = plistlib.loads((FIXTURE / "Device" / "SysInfoExtended").read_bytes())
    methods = identification_methods(
        family_id=data["FamilyID"], serial=data["SerialNumber"],
    )
    assert methods["family_id"] == ("iPod Nano", "7th Gen")
    assert methods["serial_suffix"] == ("iPod Nano", "7th Gen")
    assert methods["family_id"] == methods["serial_suffix"]


@skip_no_fixture
def test_via_serial_sola_tambien_resuelve():
    data = plistlib.loads((FIXTURE / "Device" / "SysInfoExtended").read_bytes())
    methods = identification_methods(serial=data["SerialNumber"])
    assert methods["serial_suffix"] == ("iPod Nano", "7th Gen")


@skip_no_fixture
def test_no_escribe_en_el_fixture(mount):
    antes = {p: p.stat().st_mtime_ns for p in FIXTURE.rglob("*") if p.is_file()}
    read_device_info(mount)
    read_device_info(mount, use_usb=True)
    despues = {p: p.stat().st_mtime_ns for p in FIXTURE.rglob("*") if p.is_file()}
    assert antes == despues


@skip_no_fixture
def test_use_usb_no_cambia_ni_rompe(mount):
    a = read_device_info(mount, use_usb=False)
    b = read_device_info(mount, use_usb=True)
    assert (a.family, a.generation, a.checksum) == (b.family, b.generation, b.checksum)


def test_degrada_a_parcial_sin_excepcion(tmp_path):
    dev = tmp_path / "IPOD" / "iPod_Control" / "Device"
    dev.mkdir(parents=True)
    (dev / "SysInfoExtended").write_bytes(b"basura no plist")
    info = read_device_info(tmp_path / "IPOD")
    assert isinstance(info, DeviceInfo)
    assert info.partial is True
    assert info.family is None
    assert info.capabilities is None
    assert info.checksum is None


def test_family_id_conocido_sin_serial_resuelve(tmp_path):
    dev = tmp_path / "IPOD" / "iPod_Control" / "Device"
    dev.mkdir(parents=True)
    (dev / "SysInfoExtended").write_bytes(
        plistlib.dumps({"FamilyID": 18, "FireWireGUID": "000A27002484DDFB"})
    )
    info = read_device_info(tmp_path / "IPOD")
    assert info.identified_by == "family_id"
    assert (info.family, info.generation) == ("iPod Nano", "7th Gen")
    assert info.partial is False
    assert info.capacity is None


def test_volumen_sin_device_degrada(tmp_path):
    (tmp_path / "IPOD" / "iPod_Control").mkdir(parents=True)
    info = read_device_info(tmp_path / "IPOD")
    assert info.partial is True
    assert info.firewire_guid is None
