"""Tests de cicada/ipod/util/fsfilter — filtro de artefactos macOS/FAT32.

No requieren iPod conectado: se construyen árboles temporales con tmp_path.
"""
import os
from pathlib import Path

import pytest

from cicada.ipod.util import fsfilter
from cicada.ipod.util.fsfilter import (
    filter_names,
    filter_paths,
    is_macos_artifact,
)

# Artefactos que DEBEN filtrarse (nombre pelado).
ARTIFACTS = [
    "._SysInfo",            # fork AppleDouble
    "._SysInfoExtended",
    "._",                   # prefijo a secas
    "._iTunesCDB",
    ".DS_Store",
    ".Spotlight-V100",
    ".fseventsd",
    ".Trashes",
]

# Variantes de capitalización (FAT32 no preserva mayúsculas de forma fiable).
CASE_VARIANTS = [
    ".ds_store",
    ".DS_STORE",
    ".Ds_StOrE",
    ".SPOTLIGHT-V100",
    ".FSEventsD",
    ".TRASHES",
]

# Nombres legítimos del iPod que NO deben filtrarse.
KEEP = [
    "iTunesCDB",
    "Library.itdb",
    "Locations.itdb.cbk",
    "Music",
    "F00",
    "song.mp3",
    "SysInfo",
    "SysInfoExtended",
    ".itdb_hidden",         # dotfile normal: NO es artefacto (no empieza por "._")
    "my._file.mp3",         # "._" en medio, no al inicio
    ".Spotlight",           # parecido pero no exacto
    "DS_Store",             # sin el punto inicial
]


# --- Predicado ---------------------------------------------------------------

@pytest.mark.parametrize("name", ARTIFACTS + CASE_VARIANTS)
def test_artifacts_detectados(name):
    assert is_macos_artifact(name) is True


@pytest.mark.parametrize("name", KEEP)
def test_legitimos_no_detectados(name):
    assert is_macos_artifact(name) is False


def test_case_insensitive_explicito():
    # El mismo artefacto en tres capitalizaciones -> siempre detectado.
    for variant in (".DS_Store", ".ds_store", ".DS_STORE"):
        assert is_macos_artifact(variant) is True


def test_prefijo_appledouble_case_insensitive():
    assert is_macos_artifact("._Foo") is True
    assert is_macos_artifact("._FOO") is True


# --- Aplica a archivos Y directorios (solo mira el nombre) -------------------

def test_aplica_a_rutas_completas():
    assert is_macos_artifact("/Volumes/IPOD/.Spotlight-V100") is True
    assert is_macos_artifact("/Volumes/IPOD/iPod_Control/._SysInfo") is True
    assert is_macos_artifact("/Volumes/IPOD/iPod_Control/iTunes/iTunesCDB") is False


def test_acepta_str_y_pathlike():
    assert is_macos_artifact(Path("/Volumes/IPOD/.DS_Store")) is True
    assert is_macos_artifact(Path("Music")) is False
    # str y Path del mismo valor coinciden
    assert is_macos_artifact("._x") == is_macos_artifact(Path("._x"))


# --- Helper sobre iterables --------------------------------------------------

def test_filter_paths_conserva_orden_y_descarta_artefactos():
    entrada = ["iTunesCDB", ".DS_Store", "Music", "._SysInfo", "song.mp3", ".Trashes"]
    assert list(filter_paths(entrada)) == ["iTunesCDB", "Music", "song.mp3"]


def test_filter_paths_es_perezoso():
    import types
    resultado = filter_paths(["a", ".DS_Store", "b"])
    assert isinstance(resultado, types.GeneratorType)
    assert list(resultado) == ["a", "b"]


def test_filter_paths_conserva_tipo_path():
    entrada = [Path("Music"), Path(".DS_Store"), Path("song.mp3")]
    salida = list(filter_paths(entrada))
    assert salida == [Path("Music"), Path("song.mp3")]
    assert all(isinstance(p, Path) for p in salida)


def test_filter_names_equivalente():
    entrada = ["A", "._B", "C", ".fseventsd"]
    assert list(filter_names(entrada)) == ["A", "C"]


def test_filter_paths_vacio():
    assert list(filter_paths([])) == []


# --- Contra un directorio temporal real (sin iPod) ---------------------------

def test_contra_directorio_temporal(tmp_path):
    # Recrea el ruido típico de macOS junto a datos reales del iPod.
    (tmp_path / "iTunesCDB").write_bytes(b"data")
    (tmp_path / "Library.itdb").write_bytes(b"data")
    (tmp_path / "._SysInfo").write_bytes(b"fork")
    (tmp_path / ".DS_Store").write_bytes(b"junk")
    (tmp_path / ".Trashes").mkdir()          # artefacto que es DIRECTORIO
    (tmp_path / ".Spotlight-V100").mkdir()
    (tmp_path / ".fseventsd").mkdir()
    (tmp_path / "Music").mkdir()             # directorio legítimo
    (tmp_path / "Music" / "._track.mp3").write_bytes(b"fork")

    # Escaneo con os.scandir -> DirEntry es os.PathLike, filter_paths lo acepta.
    visibles = sorted(e.name for e in filter_paths(os.scandir(tmp_path)))
    assert visibles == ["Library.itdb", "Music", "iTunesCDB"]

    # Filtra correctamente tanto archivos como directorios.
    todos = sorted(p.name for p in tmp_path.iterdir())
    assert ".Trashes" in todos and ".DS_Store" in todos  # existen en disco
    filtrados = sorted(p.name for p in filter_paths(tmp_path.iterdir()))
    assert filtrados == ["Library.itdb", "Music", "iTunesCDB"]


def test_directorio_anidado_con_forks(tmp_path):
    sub = tmp_path / "iPod_Control" / "iTunes"
    sub.mkdir(parents=True)
    (sub / "iTunesCDB").write_bytes(b"x")
    (sub / "._iTunesCDB").write_bytes(b"x")
    (sub / ".DS_Store").write_bytes(b"x")

    filtrados = sorted(p.name for p in filter_paths(sub.iterdir()))
    assert filtrados == ["iTunesCDB"]


def test_constantes_publicas_coherentes():
    # ARTIFACT_NAMES documenta los nombres tal cual; la detección los reconoce.
    for name in fsfilter.ARTIFACT_NAMES:
        assert is_macos_artifact(name) is True
    assert fsfilter.APPLEDOUBLE_PREFIX == "._"
