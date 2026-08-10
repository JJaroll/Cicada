"""Tests de verificación HASHAB (Etapa 3b) — el go/no-go de la Fase 2.

Criterio de aceptación: verify_hashab reproduce la firma HASHAB existente en el
iTunesCDB real del fixture (Nano 7G). Requiere wasmtime.
"""
import sys
from pathlib import Path

import pytest

wasmtime = pytest.importorskip("wasmtime", reason="wasmtime no instalado")

from cicada.ipod.db.writer.verify import canonical_hashab_sha1, verify_hashab

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "nano7g"
CDB = FIXTURE / "iTunes" / "iTunesCDB"
GUID = "000A27002484DDFB"
skip_no_fixture = pytest.mark.skipif(not CDB.exists(), reason="fixture no presente")


@skip_no_fixture
def test_verify_hashab_reproduce_la_firma_existente():
    r = verify_hashab(CDB.read_bytes(), bytes.fromhex(GUID))
    assert r.valid is True
    assert r.stored == r.computed
    assert len(r.stored) == 57


@skip_no_fixture
def test_firma_empieza_por_marcador_conocido():
    # La firma HASHAB del Nano 7G empieza por 0x0300 (marcador) y termina en 0x57.
    r = verify_hashab(CDB.read_bytes(), bytes.fromhex(GUID))
    assert r.stored[:2] == bytes.fromhex("0300")
    assert r.stored[-1] == 0x57


@skip_no_fixture
def test_guid_incorrecto_no_valida():
    r = verify_hashab(CDB.read_bytes(), bytes.fromhex("DEADBEEFDEADBEEF"))
    assert r.valid is False
    assert r.stored != r.computed          # pero la firma almacenada se conserva


@skip_no_fixture
def test_sha1_canonico_es_determinista():
    data = CDB.read_bytes()
    assert canonical_hashab_sha1(data) == canonical_hashab_sha1(data)
    assert len(canonical_hashab_sha1(data)) == 20


@skip_no_fixture
@pytest.mark.skipif(sys.platform == "win32", reason="symlinks no POSIX")
def test_integracion_guid_desde_device_info(tmp_path):
    # El GUID que verify necesita sale de device_info leyendo solo el volumen.
    from cicada.ipod.device.device_info import read_device_info
    mount = tmp_path / "IPOD"
    mount.mkdir()
    (mount / "iPod_Control").symlink_to(FIXTURE)
    info = read_device_info(mount)
    assert info.firewire_guid == GUID
    assert info.checksum.name == "HASHAB"
    r = verify_hashab(CDB.read_bytes(), bytes.fromhex(info.firewire_guid))
    assert r.valid is True
