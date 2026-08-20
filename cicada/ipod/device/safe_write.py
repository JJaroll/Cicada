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
from cicada.ipod.device.write_guard import IPOD_CONTROL_DIRNAME, assert_within_ipod_control

__all__ = [
    "guarded_durable_replace",
    "guarded_durable_publish_new",
    "guarded_durable_unlink",
]


def guarded_durable_replace(
    source: str | os.PathLike,
    target: str | os.PathLike,
    mount: str | os.PathLike,
    *,
    root: str = IPOD_CONTROL_DIRNAME,
) -> None:
    """`durable_replace` confinado: rechaza un ``target`` fuera de ``<mount>/root/``.

    Resuelve symlinks y ``..`` (vía ``assert_within_ipod_control``) antes de
    delegar en :func:`durability.durable_replace`. ``root`` default
    ``iPod_Control`` — pasar ``write_guard.PHOTOS_DIRNAME`` explícitamente
    para escrituras a ``Photos/`` (Etapa 6h, fuera de ``iPod_Control/``).

    :raises PathOutsideIpodControlError: si el destino cae fuera del árbol.
    """
    assert_within_ipod_control(target, mount, root=root)
    durability.durable_replace(source, target)


def guarded_durable_publish_new(
    source: str | os.PathLike,
    target: str | os.PathLike,
    mount: str | os.PathLike,
    *,
    root: str = IPOD_CONTROL_DIRNAME,
) -> bool:
    """`durable_publish_new` confinado (publica sin sobrescribir un existente)."""
    assert_within_ipod_control(target, mount, root=root)
    return durability.durable_publish_new(source, target)


def guarded_durable_unlink(
    path: str | os.PathLike,
    mount: str | os.PathLike,
    *,
    missing_ok: bool = False,
    root: str = IPOD_CONTROL_DIRNAME,
) -> None:
    """`durable_unlink` confinado: rechaza borrar fuera de ``<mount>/root/``."""
    assert_within_ipod_control(path, mount, root=root)
    durability.durable_unlink(path, missing_ok=missing_ok)
