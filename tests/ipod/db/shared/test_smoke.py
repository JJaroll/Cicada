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

FIXTURE_CDB = Path(__file__).resolve().parents[3] / "fixtures" / "nano7g" / "iTunes" / "iTunesCDB"

# En el Nano 6G/7G, el iTunesCDB es una cabecera mhbd en claro seguida del cuerpo
# comprimido con zlib. Solo mhbd es visible en texto; los demás marcadores viven
# dentro del payload comprimido.
ROOT_MARKER = "mhbd"
INNER_MARKERS = ["mhsd", "mhlt", "mhit", "mhod"]


def test_paquete_carga_y_reexporta():
    # __init__ reexporta el vocabulario compartido.
    assert hasattr(shared, "FIELD_REGISTRY") or hasattr(shared, "identifier_readable_map")


def test_field_registry_tiene_los_8_chunks():
    esperado = {"mhbd", "mhit", "mhsd", "mhia", "mhii", "mhip", "mhyp", "mhod"}
    assert set(FIELD_REGISTRY) == esperado
    # Cada chunk trae una lista no vacía de FieldDef.
    for tag, fields in FIELD_REGISTRY.items():
        assert fields, f"{tag} sin campos"
        assert all(isinstance(f, FieldDef) for f in fields)


def test_u32_produce_fielddef_coherente():
    fd = _u32("prueba", 8)
    assert isinstance(fd, FieldDef)
    assert fd.size == 4
    assert fd.offset == 8
    assert "I" in fd.struct_format  # entero de 32 bits


def test_core_markers_estan_declarados_en_constants():
    for marker in [ROOT_MARKER, *INNER_MARKERS]:
        assert marker in identifier_readable_map


@pytest.mark.skipif(not FIXTURE_CDB.exists(), reason="fixture nano7g/iTunesCDB no presente")
def test_fixture_itunescdb_contiene_los_chunks_declarados():
    data = FIXTURE_CDB.read_bytes()
    assert len(data) > 0
    # El iTunesCDB arranca por el chunk raíz mhbd (en claro).
    assert data[:4] == ROOT_MARKER.encode("ascii")
    assert ROOT_MARKER in identifier_readable_map

    # El cuerpo va comprimido con zlib a partir de mhbd.header_length.
    header_length = struct.unpack_from("<I", data, 4)[0]
    payload = zlib.decompressobj().decompress(data[header_length:])
    assert len(payload) > len(data)  # realmente estaba comprimido

    # Los marcadores internos que declara constants.py aparecen en el cuerpo.
    for marker in INNER_MARKERS:
        assert marker in identifier_readable_map
        assert marker.encode("ascii") in payload, f"marcador {marker} ausente del cuerpo"
