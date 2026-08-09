"""Tests de models (vendorizado, Etapa 2a).

El Nano 7G no trae ModelNumStr en su SysInfoExtended (usa FamilyID). El lookup
por número de modelo debe degradar con elegancia cuando falta, para que la
resolución caiga en la vía family/gen (a la que apunta FamilyID en Etapa 2b).
"""
from cicada.ipod.device.capabilities import capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.models import (
    IPOD_MODELS,
    _canonical_model_number_info,
    canonicalize_model_identity,
)


def test_modelnumstr_ausente_no_rompe_canonicalize():
    # model_number=None (ModelNumStr ausente) -> no lanza; usa family/gen.
    ident = canonicalize_model_identity("iPod Nano", "7th Gen", model_number=None)
    assert ident == ("iPod Nano", "7th Gen", "")


def test_lookup_por_numero_de_modelo_degrada_con_elegancia():
    # Sin número de modelo, el lookup autoritativo devuelve None (no excepción).
    assert _canonical_model_number_info(None) is None
    assert _canonical_model_number_info("") is None
    assert _canonical_model_number_info("MODELO-INEXISTENTE") is None


def test_cadena_completa_sin_modelnumstr_resuelve_hashab():
    # La vía family/gen (a la que resuelve FamilyID) da HASHAB sin ModelNumStr.
    caps = capabilities_for_family_gen("iPod Nano", "7th Gen", model_number=None)
    assert caps is not None
    assert caps.checksum is ChecksumType.HASHAB


def test_lookup_por_numero_de_modelo_valido_sigue_funcionando():
    # Un número de modelo conocido sí resuelve (no rompimos la vía autoritativa).
    algun_modelo, esperado = next(iter(IPOD_MODELS.items()))
    ident = canonicalize_model_identity("", "", model_number=algun_modelo)
    assert ident[0] == esperado[0]   # familia
    assert ident[1] == esperado[1]   # generación
