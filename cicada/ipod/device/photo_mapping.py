"""Mapa foto→hash-visual/origen — reimplementación propia de Cicada (off-device).

iOpenPod persiste este mapa **dentro de** ``iPod_Control/iOpenPod/photo_sync.json``
(``sync/photos.py``, ``_photo_mapping_path``) — mismo problema que
``iOpenPodSysInfoAuthority`` (ver :mod:`cicada.ipod.device.authority`): un
namespace ajeno escrito en el volumen, que Music.app no reconoce.

Cicada no escribe nada de esto en el dispositivo. Esta reimplementación persiste
el mapa en ``~/.cicada/``, indexado por FireWireGUID (mismo patrón que
``consent.py``/``apply.py``/``plan.py`` vía :func:`cicada.ipod.paths.guid_hash`):

    ~/.cicada/photos/<guid_hash(guid)>/mapping.json

El "por qué" de que esto exista off-device: la base de datos de fotos del iPod
(MHII/MHLI, Etapa 6f) no guarda ``visual_hash`` ni la ruta de origen en la PC —
solo lo que cabe en el formato binario de Apple. Sin este mapa, Cicada no podría
reconocer "esta foto ya está en el dispositivo" en un sync posterior sin
recodificar y comparar cada imagen de nuevo.

Ver docs/VENDORED.md, Paquete 9, Etapa 6e.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Mapping

from cicada.ipod.paths import cicada_home, guid_hash

logger = logging.getLogger(__name__)

__all__ = [
    "PhotoMappingEntry",
    "PhotoMappingSafetyError",
    "PHOTO_SYNC_SETTINGS_KEY",
    "read_photo_mapping",
    "write_photo_mapping",
    "read_photo_sync_settings",
]

PhotoMappingEntry = dict[str, object]

#: Clave reservada dentro del mapa para la configuración de sync (no es un
#: image_id real — los image_id del dispositivo son numéricos, ``>= 100``,
#: ver ``_MIN_PHOTO_ID`` en sync/photos.py de iOpenPod).
PHOTO_SYNC_SETTINGS_KEY = "__photo_sync_settings__"


class PhotoMappingSafetyError(RuntimeError):
    """El mapa foto→hash-visual persistido no se puede leer/interpretar con
    confianza. Falla cerrado: mejor no sincronizar que sincronizar a ciegas."""


def _mapping_dir(guid: str) -> Path:
    return cicada_home() / "photos" / guid_hash(guid)


def _mapping_path(guid: str) -> Path:
    return _mapping_dir(guid) / "mapping.json"


def read_photo_mapping(guid: str) -> dict[str, PhotoMappingEntry]:
    """Lee el mapa foto→hash-visual/origen para ``guid``.

    Devuelve ``{}`` si nunca se sincronizaron fotos para este dispositivo.
    Falla cerrado (:class:`PhotoMappingSafetyError`) ante datos corruptos o
    con forma inesperada, en vez de tratarlos como "mapa vacío" — un mapa
    vacío leído por error implica perder la deduplicación por hash visual en
    el próximo sync (fotos re-subidas como si fueran nuevas), no un simple
    dato faltante.
    """
    path = _mapping_path(guid)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as exc:
        raise PhotoMappingSafetyError(
            f"El mapa de fotos en {path} no se pudo leer de forma segura: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise PhotoMappingSafetyError(f"El mapa de fotos en {path} tiene una forma inválida.")
    if any(not isinstance(key, str) or not isinstance(value, dict) for key, value in data.items()):
        raise PhotoMappingSafetyError(f"El mapa de fotos en {path} contiene entradas inválidas.")
    return data


def read_photo_sync_settings(guid: str) -> dict[str, bool]:
    """Configuración de sync de fotos persistida (rotación/ajuste de miniaturas),
    o los defaults si nunca se guardó ninguna."""
    settings = read_photo_mapping(guid).get(PHOTO_SYNC_SETTINGS_KEY)
    if not isinstance(settings, dict):
        return {"rotate_tall_photos_for_device": False, "fit_photo_thumbnails": False}
    return {
        "rotate_tall_photos_for_device": bool(settings.get("rotate_tall_photos_for_device", False)),
        "fit_photo_thumbnails": bool(settings.get("fit_photo_thumbnails", False)),
    }


def write_photo_mapping(
    guid: str,
    entries: Mapping[str, PhotoMappingEntry],
    *,
    sync_settings: Mapping[str, object] | None = None,
) -> None:
    """Persiste el mapa foto→hash-visual/origen completo para ``guid`` (off-device).

    Reemplazo atómico (tmp + ``os.replace``) sobre almacenamiento local normal
    — no hace falta la maquinaria de ``durability.py`` (fsync agresivo,
    reintentos), que existe para escrituras al propio volumen del iPod, con
    mucho más riesgo de corrupción ante un eject inesperado a mitad de escritura.
    """
    if any(not isinstance(k, str) for k in entries):
        raise ValueError("Las claves del mapa de fotos deben ser str (image_id como texto)")
    directory = _mapping_dir(guid)
    directory.mkdir(parents=True, exist_ok=True)
    payload: dict[str, PhotoMappingEntry] = dict(entries)
    payload[PHOTO_SYNC_SETTINGS_KEY] = {
        "rotate_tall_photos_for_device": bool((sync_settings or {}).get("rotate_tall_photos_for_device", False)),
        "fit_photo_thumbnails": bool((sync_settings or {}).get("fit_photo_thumbnails", False)),
    }
    path = _mapping_path(guid)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)
