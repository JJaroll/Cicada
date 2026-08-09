"""Escrituras al volumen del iPod, validadas por write_guard.

Regla de integración de Cicada: **ningún código toca el volumen del iPod sin
pasar antes por :func:`write_guard.assert_within_ipod_control`**. Las primitivas
de :mod:`durability` (vendorizadas de iOpenPod) escriben sobre el target que se
les pase, sin confinar la ruta; estos wrappers validan primero y luego delegan.

Usa siempre estas funciones —no `durability.*` directamente— para escribir en el
dispositivo.
"""
from __future__ import annotations

import os

from cicada.ipod.device import durability
from cicada.ipod.device.write_guard import assert_within_ipod_control

__all__ = [
    "guarded_durable_replace",
    "guarded_durable_publish_new",
    "guarded_durable_unlink",
]


def guarded_durable_replace(
    source: str | os.PathLike,
    target: str | os.PathLike,
    mount: str | os.PathLike,
) -> None:
    """`durable_replace` confinado: rechaza un ``target`` fuera de iPod_Control.

    Resuelve symlinks y ``..`` (vía ``assert_within_ipod_control``) antes de
    delegar en :func:`durability.durable_replace`.

    :raises PathOutsideIpodControlError: si el destino cae fuera del árbol.
    """
    assert_within_ipod_control(target, mount)
    durability.durable_replace(source, target)


def guarded_durable_publish_new(
    source: str | os.PathLike,
    target: str | os.PathLike,
    mount: str | os.PathLike,
) -> bool:
    """`durable_publish_new` confinado (publica sin sobrescribir un existente)."""
    assert_within_ipod_control(target, mount)
    return durability.durable_publish_new(source, target)


def guarded_durable_unlink(
    path: str | os.PathLike,
    mount: str | os.PathLike,
    *,
    missing_ok: bool = False,
) -> None:
    """`durable_unlink` confinado: rechaza borrar fuera de iPod_Control."""
    assert_within_ipod_control(path, mount)
    durability.durable_unlink(path, missing_ok=missing_ok)
