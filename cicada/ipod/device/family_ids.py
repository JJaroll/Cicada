"""Tabla FamilyID(int) → (familia, generación) — propia de Cicada.

iOpenPod no tiene esta tabla: identifica el dispositivo por USB PID (en vivo),
número de modelo o sufijo de serie. Cicada la necesita para **identificar el
iPod leyendo solo el volumen** (sin USB), como exige el spec — el Nano 7G no
trae `ModelNumStr` y su `SysInfoExtended` sí trae `FamilyID`.

Es **estructura de datos, no lógica**: ampliar es añadir una entrada. Cada una
documenta su procedencia y si está **verificada contra hardware real** o es
inferida (`verified=False`). Política: no se siembran adivinanzas — una entrada
confiable vale más que quince sin confirmar. Los `verified=False` se añaden
cuando alguien tenga el hardware para confirmarlos.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["FamilyEntry", "FAMILY_IDS", "lookup_family_id"]


@dataclass(frozen=True)
class FamilyEntry:
    family: str
    generation: str
    verified: bool
    source: str


FAMILY_IDS: dict[int, FamilyEntry] = {
    18: FamilyEntry(
        family="iPod Nano",
        generation="7th Gen",
        verified=True,
        source=(
            "Verificado contra iPod nano 7G real: FamilyID=18 en SysInfoExtended, "
            "confirmado de forma independiente por sufijo de serie (MD476)."
        ),
    ),
}


def lookup_family_id(family_id: int | None) -> FamilyEntry | None:
    """Entrada de la tabla para ``family_id``, o ``None`` si no está."""
    if family_id is None:
        return None
    return FAMILY_IDS.get(int(family_id))
