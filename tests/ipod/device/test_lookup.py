"""Tests de lookup (vendorizado, Etapa 2b).

Interés principal: un dispositivo SIN ModelNumStr (nuestro Nano 7G) no debe
lanzar; el lookup por número de modelo degrada a None y la resolución cae en la
vía por familia (a la que FamilyID resuelve en scanner/info).

Nota: el mapeo FamilyID(int)→("iPod Nano","7th Gen") vive en scanner/info (aún no
copiados). Aquí se prueba la vía por familia con el string ya resuelto.
"""
from cicada.ipod.device.capabilities import capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.lookup import (
    get_friendly_model_name,
    get_model_info,
    infer_generation,
    lookup_by_serial,
)


def test_sin_modelnumstr_no_lanza_y_degrada_a_none():
    # ModelNumStr ausente -> None, sin excepción.
    assert get_model_info(None) is None
    assert get_model_info("") is None
    assert lookup_by_serial("") is None
    assert lookup_by_serial(None) is None
    # get_friendly no revienta y da algo legible.
    assert get_friendly_model_name(None) == "Unknown iPod"


def test_resolucion_por_familia_sin_numero_de_modelo():
    # La vía por familia (a la que resuelve FamilyID) da HASHAB sin ModelNumStr.
    caps = capabilities_for_family_gen("iPod Nano", "7th Gen", model_number=None)
    assert caps is not None
    assert caps.checksum is ChecksumType.HASHAB


def test_infer_generation_familia_no_lanza():
    # Ambiguo -> None (no excepción); familia desconocida -> None.
    assert infer_generation("iPod Nano", capacity="16GB") in (None, "7th Gen", "1st Gen",
                                                               "3rd Gen", "4th Gen",
                                                               "5th Gen", "6th Gen")
    assert infer_generation("", capacity="") is None
    assert infer_generation("Familia Inexistente") is None


def test_numero_de_modelo_valido_sigue_resolviendo():
    # No rompimos la vía autoritativa por número de modelo.
    name, gen, capacity, color = get_model_info(next(
        m for m, v in __import__(
            "cicada.ipod.device.models", fromlist=["IPOD_MODELS"]
        ).IPOD_MODELS.items() if v[0] == "iPod Nano"
    ))
    assert name == "iPod Nano"
