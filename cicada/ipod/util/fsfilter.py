"""Filtro de archivos y directorios de artefactos macOS en FAT32."""
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
    return PurePath(os.fspath(path)).name


def is_macos_artifact(path: "str | os.PathLike") -> bool:
    # Comprueba si el archivo es un artefacto de macOS.
    name = _basename(path).lower()
    if name.startswith(APPLEDOUBLE_PREFIX):
        return True
    return name in _ARTIFACT_NAMES_LOWER


def filter_paths(paths: Iterable[T]) -> Iterator[T]:
    # Filtra rutas excluyendo los artefactos creados por macOS.
    return (p for p in paths if not is_macos_artifact(p))


def filter_names(names: Iterable[str]) -> Iterator[str]:
    # Filtra nombres de archivo ignorando artefactos de macOS.
    return (n for n in names if not is_macos_artifact(n))

