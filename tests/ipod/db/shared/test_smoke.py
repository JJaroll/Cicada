"""Smoke test del paquete vendorizado itunesdb_shared -> cicada/ipod/db/shared.

Verifica que el paquete carga bajo su nueva ruta, que el FIELD_REGISTRY se
ensambla con los 8 chunks, y que los identificadores de chunk que declara
constants.py están físicamente presentes en el iTunesCDB real del fixture
nano7g. Si el fixture no está, se salta (no falla).
"""
import struct
import zlib
from pathlib import Path

import pytest

from cicada.ipod.db import shared
from cicada.ipod.db.shared.constants import identifier_readable_map
from cicada.ipod.db.shared.field_base import FIELD_REGISTRY, FieldDef, _u32

FIXTURE_CDB = Path(__file__).resolve().parents[3] / "fixtures" / "nano7g-iopenpod" / "iTunes" / "iTunesCDB"

ROOT_MARKER = "mhbd"
INNER_MARKERS = ["mhsd", "mhlt", "mhit", "mhod"]


def test_paquete_carga_y_reexporta():
    assert hasattr(shared, "FIELD_REGISTRY") or hasattr(shared, "identifier_readable_map")


def test_field_registry_tiene_los_8_chunks():
    esperado = {"mhbd", "mhit", "mhsd", "mhia", "mhii", "mhip", "mhyp", "mhod"}
    assert set(FIELD_REGISTRY) == esperado
    for tag, fields in FIELD_REGISTRY.items():
        assert fields, f"{tag} sin campos"
        assert all(isinstance(f, FieldDef) for f in fields)


def test_u32_produce_fielddef_coherente():
    fd = _u32("prueba", 8)
    assert isinstance(fd, FieldDef)
    assert fd.size == 4
    assert fd.offset == 8
    assert "I" in fd.struct_format


def test_core_markers_estan_declarados_en_constants():
    for marker in [ROOT_MARKER, *INNER_MARKERS]:
        assert marker in identifier_readable_map


@pytest.mark.skipif(not FIXTURE_CDB.exists(), reason="fixture nano7g/iTunesCDB no presente")
def test_fixture_itunescdb_contiene_los_chunks_declarados():
    data = FIXTURE_CDB.read_bytes()
    assert len(data) > 0
    assert data[:4] == ROOT_MARKER.encode("ascii")
    assert ROOT_MARKER in identifier_readable_map

    header_length = struct.unpack_from("<I", data, 4)[0]
    payload = zlib.decompressobj().decompress(data[header_length:])
    assert len(payload) > len(data)

    for marker in INNER_MARKERS:
        assert marker in identifier_readable_map
        assert marker.encode("ascii") in payload, f"marcador {marker} ausente del cuerpo"
