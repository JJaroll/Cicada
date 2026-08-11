"""Tests de la Etapa 2d-a — identificación por USB (VPD) + orden de resolución.

Sin hardware: se mockea `vpd_iokit.query_ipod_vpd` y `volume_fingerprint`.
CICADA_HOME redirigido a tmp. Verifica: dispatcher + taxonomía de error, orden
disco→caché fuerte→USB→caché débil, usb_error no silencioso, procedencia del
GUID (write-safe vs weak), y que nada se escribe en el volumen.
"""
import plistlib
from pathlib import Path

import pytest

from cicada.ipod.device import device_info as di
from cicada.ipod.device import vpd as vpd_mod
from cicada.ipod.device import volume_id as vol_mod
from cicada.ipod.device.device_info import read_device_info
from cicada.ipod.device.volume_id import VolumeFingerprint

GUID = "000A27002484DDFB"
VPD_DICT = {"FireWireGUID": GUID, "FamilyID": 18, "SerialNumber": "DCYM32KLF0GN"}


@pytest.fixture(autouse=True)
def _cicada_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CICADA_HOME", str(tmp_path / "cicada_home"))


@pytest.fixture
def bare_ipod(tmp_path):
    """iPod restaurado por iTunes: iPod_Control/ con Device/ vacío (sin SysInfoExtended)."""
    mount = tmp_path / "IPOD"
    (mount / "iPod_Control" / "Device").mkdir(parents=True)
    (mount / "iPod_Control" / "iTunes").mkdir()
    return mount


def _mock_vpd_ok(monkeypatch):
    monkeypatch.setattr(vpd_mod, "query_vpd",
                        lambda **k: vpd_mod.VpdResult(dict(VPD_DICT), None, "iokit_scsi_vpd"))


def _mock_vpd_error(monkeypatch, msg):
    monkeypatch.setattr(vpd_mod, "query_vpd",
                        lambda **k: vpd_mod.VpdResult(None, msg, None))


def _mock_fp(monkeypatch, strength="strong", value="vol-fp-A"):
    # read_device_info importa volume_fingerprint del módulo fuente en cada llamada.
    monkeypatch.setattr(vol_mod, "volume_fingerprint",
                        lambda m: VolumeFingerprint(value=value, strength=strength, source="test"))


# --------------------------------------------------------------------------- #
# Dispatcher vpd
# --------------------------------------------------------------------------- #
def test_dispatcher_error_no_silencioso_por_plataforma(monkeypatch):
    monkeypatch.setattr(vpd_mod.sys, "platform", "linux")
    r = vpd_mod.query_vpd()
    assert r.ok is False and "Linux" in r.error


def test_dispatcher_macos_iokit_rechaza(monkeypatch):
    # El SCSITaskUserClient puede ser rechazado (acceso exclusivo / volumen montado).
    monkeypatch.setattr(vpd_mod.sys, "platform", "darwin")
    from cicada.ipod.device import vpd_iokit
    monkeypatch.setattr(vpd_iokit, "query_ipod_vpd",
                        lambda **k: (_ for _ in ()).throw(OSError("kIOReturnExclusiveAccess")))
    r = vpd_mod.query_vpd()
    assert r.ok is False and "SCSITaskUserClient" in r.error


def test_dispatcher_macos_dispositivo_no_encontrado(monkeypatch):
    monkeypatch.setattr(vpd_mod.sys, "platform", "darwin")
    from cicada.ipod.device import vpd_iokit
    monkeypatch.setattr(vpd_iokit, "query_ipod_vpd", lambda **k: None)
    r = vpd_mod.query_vpd()
    assert r.ok is False and "no encontrado" in r.error


# --------------------------------------------------------------------------- #
# Orden de resolución
# --------------------------------------------------------------------------- #
def test_usb_resuelve_guid_cuando_no_hay_disco(bare_ipod, monkeypatch):
    _mock_fp(monkeypatch, "strong")
    _mock_vpd_ok(monkeypatch)
    info = read_device_info(bare_ipod, use_usb=True)
    assert info.firewire_guid == GUID
    assert info.guid_provenance == "usb"
    assert info.family == "iPod Nano" and info.generation == "7th Gen"
    assert info.checksum.name == "HASHAB"
    assert info.usb_error is None
    assert info.guid_is_write_safe is True


def test_usb_cachea_y_segunda_sesion_usa_cache_fuerte_sin_usb(bare_ipod, monkeypatch):
    _mock_fp(monkeypatch, "strong")
    _mock_vpd_ok(monkeypatch)
    # 1ª sesión: USB.
    a = read_device_info(bare_ipod, use_usb=True)
    assert a.guid_provenance == "usb"
    # 2ª sesión: USB DEBE fallar si se llama (no debería llamarse).
    def _must_not_call(**k):
        raise AssertionError("no debe abrir USB: hay caché fuerte")
    monkeypatch.setattr(vpd_mod, "query_vpd", _must_not_call)
    b = read_device_info(bare_ipod, use_usb=True)
    assert b.firewire_guid == GUID
    assert b.guid_provenance == "cache_strong"
    assert b.guid_is_write_safe is True


def test_disco_tiene_prioridad_sobre_todo(tmp_path, monkeypatch):
    # Con SysInfoExtended en disco, ni caché ni USB se consultan.
    mount = tmp_path / "IPOD"
    dev = mount / "iPod_Control" / "Device"
    dev.mkdir(parents=True)
    dev.joinpath("SysInfoExtended").write_bytes(
        plistlib.dumps({"FireWireGUID": GUID, "FamilyID": 18}))
    monkeypatch.setattr(vpd_mod, "query_vpd",
                        lambda **k: (_ for _ in ()).throw(AssertionError("USB no debe usarse")))
    info = read_device_info(mount, use_usb=True)
    assert info.guid_provenance == "disk"
    assert info.firewire_guid == GUID


# --------------------------------------------------------------------------- #
# usb_error no silencioso
# --------------------------------------------------------------------------- #
def test_usb_error_se_reporta(bare_ipod, monkeypatch):
    _mock_fp(monkeypatch, "strong")
    _mock_vpd_error(monkeypatch, "IOKit rechazó el SCSITaskUserClient: busy")
    info = read_device_info(bare_ipod, use_usb=True)
    assert info.firewire_guid is None
    assert info.partial is True
    assert info.usb_error == "IOKit rechazó el SCSITaskUserClient: busy"
    assert info.sources.get("usb") == info.usb_error


# --------------------------------------------------------------------------- #
# Puntero débil: USB primero, y no write-safe
# --------------------------------------------------------------------------- #
def test_puntero_debil_por_debajo_de_usb(bare_ipod, monkeypatch):
    from cicada.ipod.device import authority
    _mock_fp(monkeypatch, "weak", value="weak-fp")
    # Sembrar un puntero débil que resolvería a un GUID.
    authority.write_guid_pointer("weak-fp", GUID, strength="weak")
    authority.store_sysinfo_extended_for_guid(GUID, plistlib.dumps({"FireWireGUID": GUID, "FamilyID": 18}))
    # use_usb=True: debe intentar USB ANTES del puntero débil.
    _mock_vpd_ok(monkeypatch)
    info = read_device_info(bare_ipod, use_usb=True)
    assert info.guid_provenance == "usb"        # no cache_weak


def test_puntero_debil_solo_sin_usb_y_marcado(bare_ipod, monkeypatch):
    from cicada.ipod.device import authority
    _mock_fp(monkeypatch, "weak", value="weak-fp")
    authority.write_guid_pointer("weak-fp", GUID, strength="weak")
    authority.store_sysinfo_extended_for_guid(GUID, plistlib.dumps({"FireWireGUID": GUID, "FamilyID": 18}))
    info = read_device_info(bare_ipod, use_usb=False)   # sin USB
    assert info.firewire_guid == GUID
    assert info.guid_provenance == "cache_weak"
    assert info.sources.get("firewire_guid_strength") == "weak"
    assert info.guid_is_write_safe is False            # NO apto para firmar en Fase 2


# --------------------------------------------------------------------------- #
# Nada se escribe en el volumen
# --------------------------------------------------------------------------- #
def test_usb_no_escribe_en_el_volumen(bare_ipod, monkeypatch):
    _mock_fp(monkeypatch, "strong")
    _mock_vpd_ok(monkeypatch)
    antes = {p for p in bare_ipod.rglob("*")}
    read_device_info(bare_ipod, use_usb=True)
    despues = {p for p in bare_ipod.rglob("*")}
    assert antes == despues            # ni un archivo nuevo en el iPod
    # ...pero sí cacheó off-device (en CICADA_HOME).
    import os
    home = Path(os.environ["CICADA_HOME"])
    assert any(home.rglob("SysInfoExtended"))
    assert any(home.rglob("index/*.json"))


# --------------------------------------------------------------------------- #
# Fingerprint: fuerte vs débil
# --------------------------------------------------------------------------- #
def test_volume_fingerprint_fuerte_desde_diskutil(monkeypatch, tmp_path):
    monkeypatch.setattr(vol_mod.sys, "platform", "darwin")
    monkeypatch.setattr(vol_mod, "_diskutil_info",
                        lambda m, **k: {"VolumeUUID": "ABCD-1234", "DeviceNode": "/dev/disk4s1", "VolumeName": "IPOD"})
    fp = vol_mod.volume_fingerprint(tmp_path)
    assert fp.strength == "strong" and fp.source == "diskutil_volumeuuid"


def test_volume_fingerprint_debil_si_no_hay_uuid(monkeypatch, tmp_path):
    monkeypatch.setattr(vol_mod.sys, "platform", "darwin")
    monkeypatch.setattr(vol_mod, "_diskutil_info",
                        lambda m, **k: {"VolumeUUID": "00000000-0000-0000-0000-000000000000",
                                        "DeviceNode": "/dev/disk4s1", "VolumeName": "iPod"})
    fp = vol_mod.volume_fingerprint(tmp_path)
    assert fp.strength == "weak" and fp.source == "devicenode+volumename"
