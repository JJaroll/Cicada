"""Tests de photo_mapping (Etapa 6e — reimplementación off-device de
iOpenPod's photo_sync.json, mismo patrón que authority.py).

Todo con tmp_path: ~/.cicada redirigido por CICADA_HOME. Sin dispositivo real
— este módulo nunca toca el volumen, por diseño (esa es la razón de ser del
rediseño off-device).
"""
import json
from pathlib import Path

import pytest

from cicada.ipod.device.photo_mapping import (
    PHOTO_SYNC_SETTINGS_KEY,
    PhotoMappingSafetyError,
    read_photo_mapping,
    read_photo_sync_settings,
    write_photo_mapping,
)
from cicada.ipod.paths import cicada_home, guid_hash

GUID = "000A27002484DDFB"


@pytest.fixture(autouse=True)
def _cicada_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CICADA_HOME", str(tmp_path / "cicada_home"))


def test_mapa_vacio_si_nunca_se_sincronizo():
    assert read_photo_mapping(GUID) == {}


def test_round_trip_de_entradas():
    entries = {
        "100": {"visual_hash": "abc123", "source_path": "/Users/j/Pictures/a.jpg", "display_name": "a.jpg"},
        "101": {"visual_hash": "def456", "source_path": "/Users/j/Pictures/b.jpg", "display_name": "b.jpg"},
    }
    write_photo_mapping(GUID, entries)
    read_back = read_photo_mapping(GUID)
    assert read_back["100"] == entries["100"]
    assert read_back["101"] == entries["101"]


def test_settings_por_defecto_si_nunca_se_guardaron():
    write_photo_mapping(GUID, {})
    assert read_photo_sync_settings(GUID) == {
        "rotate_tall_photos_for_device": False,
        "fit_photo_thumbnails": False,
    }


def test_round_trip_de_settings():
    write_photo_mapping(GUID, {}, sync_settings={"rotate_tall_photos_for_device": True, "fit_photo_thumbnails": True})
    assert read_photo_sync_settings(GUID) == {
        "rotate_tall_photos_for_device": True,
        "fit_photo_thumbnails": True,
    }


def test_settings_no_se_filtran_como_entrada_de_foto():
    write_photo_mapping(GUID, {"100": {"visual_hash": "x", "source_path": "", "display_name": ""}})
    entries = read_photo_mapping(GUID)
    assert PHOTO_SYNC_SETTINGS_KEY in entries
    assert "100" in entries
    assert len(entries) == 2


def test_indexado_por_guid_no_por_montaje():
    """Dos GUIDs distintos nunca comparten almacenamiento — el mismo iPod
    montado en rutas distintas debe resolver al mismo mapa, y dos iPods
    distintos nunca deben mezclarse."""
    other_guid = "AABBCCDDEEFF0011"
    write_photo_mapping(GUID, {"100": {"visual_hash": "a", "source_path": "", "display_name": ""}})
    write_photo_mapping(other_guid, {"200": {"visual_hash": "b", "source_path": "", "display_name": ""}})
    assert "100" in read_photo_mapping(GUID)
    assert "100" not in read_photo_mapping(other_guid)
    assert "200" in read_photo_mapping(other_guid)


def test_carpeta_ofuscada_con_guid_hash():
    write_photo_mapping(GUID, {})
    expected_dir = cicada_home() / "photos" / guid_hash(GUID)
    assert expected_dir.is_dir()
    assert (expected_dir / "mapping.json").is_file()
    # El GUID crudo no debe aparecer en el nombre de la carpeta.
    assert GUID not in str(expected_dir)


def test_escritura_es_atomica_no_deja_temp_huerfano():
    write_photo_mapping(GUID, {"100": {"visual_hash": "a", "source_path": "", "display_name": ""}})
    directory = cicada_home() / "photos" / guid_hash(GUID)
    leftovers = list(directory.glob("*.tmp"))
    assert leftovers == []


def test_falla_cerrado_ante_json_malformado():
    write_photo_mapping(GUID, {})
    path = cicada_home() / "photos" / guid_hash(GUID) / "mapping.json"
    path.write_text("{not valid json")
    with pytest.raises(PhotoMappingSafetyError):
        read_photo_mapping(GUID)


def test_falla_cerrado_ante_forma_invalida():
    write_photo_mapping(GUID, {})
    path = cicada_home() / "photos" / guid_hash(GUID) / "mapping.json"
    path.write_text(json.dumps(["no", "es", "un", "dict"]))
    with pytest.raises(PhotoMappingSafetyError):
        read_photo_mapping(GUID)


def test_falla_cerrado_ante_entrada_no_dict():
    write_photo_mapping(GUID, {})
    path = cicada_home() / "photos" / guid_hash(GUID) / "mapping.json"
    path.write_text(json.dumps({"100": "no es un dict de metadata"}))
    with pytest.raises(PhotoMappingSafetyError):
        read_photo_mapping(GUID)


def test_claves_no_str_rechazadas_al_escribir():
    with pytest.raises(ValueError):
        write_photo_mapping(GUID, {100: {"visual_hash": "a", "source_path": "", "display_name": ""}})
