"""Tests de verificación HASHAB (Etapa 3b).

HALLAZGO (verificado contra hardware): nuestra implementación (el WASM de
dstaley/hashab que usa iOpenPod) reproduce las firmas escritas por **iOpenPod**,
pero **NO** las de **Apple/iTunes**. Ver docs/IPOD_INTEGRATION.md §0.3.

- Fixture ``nano7g-iopenpod`` (base escrita por iOpenPod) → verify == True.
- Fixture ``nano7g`` (base escrita por iTunes/Apple), si está presente →
  verify == False. Es el go/no-go real de la escritura de Fase 2.

Requiere wasmtime.
"""
import sys
from pathlib import Path

import pytest

wasmtime = pytest.importorskip("wasmtime", reason="wasmtime no instalado")

from cicada.ipod.db.writer.verify import canonical_hashab_sha1, verify_hashab

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "nano7g-iopenpod"
CDB = FIXTURE / "iTunes" / "iTunesCDB"
APPLE_CDB = Path(__file__).resolve().parents[3] / "fixtures" / "nano7g" / "iTunes" / "iTunesCDB"
GUID = "000A27002484DDFB"
skip_no_fixture = pytest.mark.skipif(not CDB.exists(), reason="fixture no presente")


@skip_no_fixture
def test_verify_hashab_reproduce_la_firma_de_iopenpod():
    # Reproduce la firma de una base escrita por iOpenPod (mismo WASM que la escribió).
    r = verify_hashab(CDB.read_bytes(), bytes.fromhex(GUID))
    assert r.valid is True
    assert r.stored == r.computed
    assert len(r.stored) == 57


@pytest.mark.skipif(not APPLE_CDB.exists(), reason="fixture Apple/iTunes no presente")
def test_verify_hashab_NO_reproduce_la_firma_de_apple():
    """HALLAZGO: contra una base escrita por iTunes (Apple), verify FALLA.

    Reproducimos las firmas de iOpenPod pero no las de Apple. Esto NO bloquea la
    escritura de Fase 2: verificado con hardware que el firmware del iPod acepta
    AMBAS firmas (reproduce lo que escribe iOpenPod). La divergencia solo rompe
    la compatibilidad con Music.app. Ver docs/IPOD_INTEGRATION.md §0.3.
    """
    r = verify_hashab(APPLE_CDB.read_bytes(), bytes.fromhex(GUID))
    assert r.valid is False              # nuestra firma != la de Apple
    assert r.stored != r.computed
    # La firma de Apple no comparte la estructura invariante del WASM.
    assert r.stored[4:7] != bytes.fromhex("474d48")   # 'GMH' del WASM
    assert r.computed[4:7] == bytes.fromhex("474d48")


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
