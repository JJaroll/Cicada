"""Filtro de artefactos que macOS crea sobre FAT32.

macOS ensucia los volúmenes FAT32 (como el iPod nano 7G) con archivos y
directorios propios que no pertenecen al dispositivo:

- Forks de recursos AppleDouble con prefijo ``._`` (``._SysInfo``,
  ``._SysInfoExtended``, ``._Nombre``…).
- ``.DS_Store``, ``.Spotlight-V100``, ``.fseventsd``, ``.Trashes``.

Si el parser de la base del iPod los lee como si fueran datos del dispositivo,
recibe basura. **Todo escaneo de directorios del módulo iPod debe pasar por
este filtro.** Aplica igual a archivos y a directorios: opera sobre el nombre
del último componente de la ruta, sin tocar el disco ni distinguir el tipo.

Ver docs/IPOD_INTEGRATION.md §0.5.
"""
from __future__ import annotations

import os
from pathlib import PurePath
from typing import Iterable, Iterator, TypeVar

__all__ = [
    "APPLEDOUBLE_PREFIX",
    "ARTIFACT_NAMES",
    "is_macos_artifact",
    "filter_paths",
    "filter_names",
]

APPLEDOUBLE_PREFIX = "._"

ARTIFACT_NAMES = frozenset({
    ".DS_Store",
    ".Spotlight-V100",
    ".fseventsd",
    ".Trashes",
})

_ARTIFACT_NAMES_LOWER = frozenset(name.lower() for name in ARTIFACT_NAMES)

T = TypeVar("T", str, os.PathLike)


def _basename(path: "str | os.PathLike") -> str:
    """Último componente de la ruta, aceptando ``str`` o ``os.PathLike``.

    Para un nombre suelto (sin separadores) lo devuelve tal cual, así el filtro
    sirve tanto para entradas de ``os.scandir``/``listdir`` (nombres pelados)
    como para rutas completas.
    """
    return PurePath(os.fspath(path)).name


def is_macos_artifact(path: "str | os.PathLike") -> bool:
    """``True`` si ``path`` es un artefacto de macOS/FAT32 que debe ignorarse.

    Considera el último componente de la ruta:

    - cualquier nombre que empiece por ``._`` (fork AppleDouble), o
    - uno de :data:`ARTIFACT_NAMES` (sin distinguir mayúsculas).

    Funciona igual para archivos y directorios; solo mira el nombre.
    """
    name = _basename(path).lower()
    if name.startswith(APPLEDOUBLE_PREFIX):
        return True
    return name in _ARTIFACT_NAMES_LOWER


def filter_paths(paths: Iterable[T]) -> Iterator[T]:
    """Filtra un iterable de rutas, descartando los artefactos de macOS/FAT32.

    Devuelve un iterador *perezoso* que emite los elementos que **no** son
    artefactos, en el mismo orden y conservando su tipo original (``str`` o
    ``Path``). Es el helper que deben usar los escaneos del módulo iPod::

        for entry in filter_paths(os.scandir(mount)):
            ...

    (funciona con cualquier objeto convertible a ruta vía ``os.fspath``, lo que
    incluye los ``os.DirEntry`` de ``os.scandir``).
    """
    return (p for p in paths if not is_macos_artifact(p))


def filter_names(names: Iterable[str]) -> Iterator[str]:
    """Variante de :func:`filter_paths` para iterables de nombres sueltos.

    Idéntica en comportamiento (``filter_paths`` ya acepta nombres), se ofrece
    por claridad en los sitios que trabajan con ``os.listdir`` u otras fuentes
    de nombres en vez de rutas.
    """
    return (n for n in names if not is_macos_artifact(n))
