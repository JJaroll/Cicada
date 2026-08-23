"""Tests de la Etapa 3a — parseo del iTunesCDB real + Play Counts.

Contra el fixture nano7g (comprimido zlib), presentado como mount con symlink.
Criterio de aceptación #1: listar tracks y playlists reales.
"""
import struct
import sys
from pathlib import Path

import pytest

from cicada.ipod.db.parser import (
    decompress_itunescdb,
    load_ipod_library,
    parse_playcounts,
)

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "nano7g-iopenpod"
CDB = FIXTURE / "iTunes" / "iTunesCDB"
skip_no_fixture = pytest.mark.skipif(
    not CDB.exists() or sys.platform == "win32",
    reason="fixture no presente (o symlinks no POSIX)",
)


@pytest.fixture
def mount(tmp_path):
    m = tmp_path / "IPOD"
    m.mkdir()
    (m / "iPod_Control").symlink_to(FIXTURE)
    return m


@pytest.fixture
def library(mount):
    return load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))


@skip_no_fixture
def test_decompress_itunescdb():
    raw = CDB.read_bytes()
    out = decompress_itunescdb(raw)
    assert out[:4] == b"mhbd"
    assert len(out) > len(raw)
    header_len = struct.unpack_from("<I", raw, 0x04)[0]
    assert out[:header_len] == raw[:header_len]


@skip_no_fixture
def test_lista_25_tracks(library):
    tracks = library["mhlt"]
    assert len(tracks) == 25
    t0 = tracks[0]
    assert t0["Title"] == "LoveDrug (Apple Music Live)"
    assert t0["Artist"] == "Lady Gaga"
    assert t0["Filetype"] == "MP3"
    assert t0["Location"].endswith("JPOM.mp3")
    assert all(t.get("Title") for t in tracks)
    assert all(t.get("Artist") for t in tracks)


@skip_no_fixture
def test_lista_3_playlists(library):
    pls = library["mhlp"]
    assert len(pls) == 3
    master = next(p for p in pls if p.get("Title") == "iPod")
    assert len(master["items"]) == 25
    otras = [p for p in pls if p.get("Title") != "iPod"]
    assert len(otras) == 2
    assert all(len(p["items"]) > 0 for p in otras)


@skip_no_fixture
def test_play_counts_existe_con_25_entradas(mount):
    pc = parse_playcounts(str(mount / "iPod_Control" / "iTunes" / "Play Counts"))
    assert pc is not None
    assert len(pc) == 25


@skip_no_fixture
def test_play_counts_sin_datos_reales(mount):
    pc = parse_playcounts(str(mount / "iPod_Control" / "iTunes" / "Play Counts"))
    assert all(e.play_count == 0 for e in pc)
    assert all(e.skip_count == 0 for e in pc)
    assert all(e.rating == -1 for e in pc)
    assert len({e.last_played_mac for e in pc}) == 1


@skip_no_fixture
def test_play_counts_corresponde_con_tracks(library, mount):
    pc = parse_playcounts(str(mount / "iPod_Control" / "iTunes" / "Play Counts"))
    assert len(pc) == len(library["mhlt"]) == 25
    assert all(t.get("play_count_1", 0) == 0 for t in library["mhlt"])


@skip_no_fixture
def test_mount_explicito_funciona(mount):
    data = load_ipod_library(
        str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount),
    )
    assert data is not None and len(data["mhlt"]) == 25


def test_archivo_inexistente_devuelve_none(tmp_path):
    assert load_ipod_library(str(tmp_path / "no_existe")) is None


@skip_no_fixture
def test_no_escribe_en_el_fixture(mount):
    antes = {p: p.stat().st_mtime_ns for p in FIXTURE.rglob("*") if p.is_file()}
    load_ipod_library(str(mount / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(mount))
    despues = {p: p.stat().st_mtime_ns for p in FIXTURE.rglob("*") if p.is_file()}
    assert antes == despues
