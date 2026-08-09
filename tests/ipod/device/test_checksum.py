"""Tests de checksum (vendorizado, Etapa 2a).

Resolución del esquema de hashing para el Nano 7G. Hallazgo importante: el
esquema HASHAB del Nano 7G NO se resuelve leyendo mhbd[0x30] (ahí el fixture
guarda 3, que no está en el mapa wire), sino por capacidad (family/gen).
"""
import struct
from pathlib import Path

import pytest

from cicada.ipod.device.capabilities import checksum_type_for_family_gen
from cicada.ipod.device.checksum import (
    CHECKSUM_MHBD_SCHEME,
    MHBD_SCHEME_TO_CHECKSUM,
    ChecksumType,
)

FIXTURE_CDB = Path(__file__).resolve().parents[2] / "fixtures" / "nano7g" / "iTunes" / "iTunesCDB"


def test_mapa_wire_hashab_es_4():
    # HASHAB es enum 3 pero valor de wire 4 en el campo hashing_scheme.
    assert CHECKSUM_MHBD_SCHEME[ChecksumType.HASHAB] == 4
    assert MHBD_SCHEME_TO_CHECKSUM[4] is ChecksumType.HASHAB
    assert ChecksumType.HASHAB.value == 3


def test_mapa_wire_completo():
    assert MHBD_SCHEME_TO_CHECKSUM == {
        0: ChecksumType.NONE,
        1: ChecksumType.HASH58,
        2: ChecksumType.HASH72,
        4: ChecksumType.HASHAB,
    }


def test_hashab_se_resuelve_por_family_gen_no_por_mhbd():
    # La vía autoritativa para nuestro dispositivo: por capacidad.
    assert checksum_type_for_family_gen("iPod Nano", "7th Gen") is ChecksumType.HASHAB


@pytest.mark.skipif(not FIXTURE_CDB.exists(), reason="fixture nano7g/iTunesCDB no presente")
def test_fixture_mhbd_0x30_no_basta_para_hashab():
    """Documenta el hallazgo: en el iTunesCDB real, mhbd[0x30] = 3, que NO está
    en el mapa wire (espera 4 para HASHAB). Por eso HASHAB se determina por
    capacidad, no leyendo este campo."""
    data = FIXTURE_CDB.read_bytes()
    scheme = struct.unpack_from("<H", data, 0x30)[0]
    assert scheme == 3
    # 3 no es una clave del mapa wire -> no resuelve a HASHAB directamente.
    assert MHBD_SCHEME_TO_CHECKSUM.get(scheme) is not ChecksumType.HASHAB
    assert MHBD_SCHEME_TO_CHECKSUM.get(scheme) is None
    # La firma HASHAB (57 bytes) sí vive en 0xAB del header.
    assert len(data) > 0xAB + 57
