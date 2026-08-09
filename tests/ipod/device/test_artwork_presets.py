"""Smoke test de artwork_presets (vendorizado, Etapa 2a).

Aún no se usa (el artwork llega en Fase 4); solo se comprueba que carga y que
la tabla que consume capabilities está bien formada.
"""
from cicada.ipod.device.artwork_presets import ARTWORK_FORMATS_BY_ID, ArtworkFormat


def test_tabla_carga_y_no_esta_vacia():
    assert isinstance(ARTWORK_FORMATS_BY_ID, dict)
    assert len(ARTWORK_FORMATS_BY_ID) > 0


def test_entradas_son_artworkformat_con_id_coherente():
    for fmt_id, fmt in ARTWORK_FORMATS_BY_ID.items():
        assert isinstance(fmt, ArtworkFormat)
        assert fmt.format_id == fmt_id          # la clave coincide con el id
        assert fmt.width > 0 and fmt.height > 0


def test_formatos_del_nano7g_presentes():
    # capabilities del Nano 7G referencia estos IDs de foto (1005, 1007).
    assert 1005 in ARTWORK_FORMATS_BY_ID
    assert 1007 in ARTWORK_FORMATS_BY_ID
