"""Tests del pipeline de copia de audio al iPod (media.py) — sin dispositivo real.

Solo AÑADE archivos con nombres únicos; nunca sobrescribe audio existente; y en
caso de fallo limpia lo ya copiado (rollback).
"""
import random
from pathlib import Path

import pytest

from cicada.ipod.db.coordinator.media import (
    MediaAssignment,
    assign_location,
    assign_media_locations,
    cleanup_media,
    copy_media,
    existing_music_names,
)


def _fake_ipod(tmp_path: Path) -> Path:
    mount = tmp_path / "IPOD"
    (mount / "iPod_Control" / "Music").mkdir(parents=True)
    return mount


def test_assign_location_formato_y_unicidad():
    taken: set[str] = set()
    locs = [assign_location(".mp3", taken) for _ in range(200)]
    for ipod_loc, rel in locs:
        assert ipod_loc.startswith(":iPod_Control:Music:F")
        assert ipod_loc.endswith(".mp3")
        assert rel.startswith("iPod_Control/Music/F") and rel.endswith(".mp3")
    names = [rel.rsplit("/", 1)[-1] for _, rel in locs]
    assert len(names) == len(set(names)) == 200


def test_assign_location_evita_colisiones():
    taken = {"ABCD.mp3"}
    _loc, rel = assign_location(".mp3", taken, rng=random.Random(0))
    assert rel.rsplit("/", 1)[-1] != "ABCD.mp3"
    assert len(taken) == 2


def test_existing_music_names(tmp_path):
    mount = _fake_ipod(tmp_path)
    (mount / "iPod_Control/Music/F00").mkdir()
    (mount / "iPod_Control/Music/F00/XXXX.mp3").write_bytes(b"x")
    (mount / "iPod_Control/Music/F12").mkdir()
    (mount / "iPod_Control/Music/F12/YYYY.m4a").write_bytes(b"y")
    assert existing_music_names(mount) == {"XXXX.mp3", "YYYY.m4a"}


def test_assign_media_locations_no_colisiona_con_existentes(tmp_path):
    mount = _fake_ipod(tmp_path)
    (mount / "iPod_Control/Music/F00").mkdir()
    (mount / "iPod_Control/Music/F00/AAAA.mp3").write_bytes(b"x")
    srcs = [tmp_path / "a.mp3", tmp_path / "b.mp3"]
    for s in srcs:
        s.write_bytes(b"audio")
    asg = assign_media_locations(mount, srcs)
    names = {a.dest_relpath.rsplit("/", 1)[-1] for a in asg}
    assert "AAAA.mp3" not in names and len(names) == 2


def test_copy_media_copia_y_limpia(tmp_path):
    mount = _fake_ipod(tmp_path)
    src = tmp_path / "song.mp3"
    src.write_bytes(b"AUDIO-DATA")
    copied = copy_media(mount, assign_media_locations(mount, [src]))
    assert len(copied) == 1
    dest = mount / copied[0]
    assert dest.is_file() and dest.read_bytes() == b"AUDIO-DATA"
    cleanup_media(mount, copied)
    assert not dest.exists()


def test_copy_media_rollback_si_una_falla(tmp_path):
    mount = _fake_ipod(tmp_path)
    ok = tmp_path / "ok.mp3"
    ok.write_bytes(b"OK")
    asg = [
        MediaAssignment(ok, ":iPod_Control:Music:F00:AAAA.mp3", "iPod_Control/Music/F00/AAAA.mp3"),
        MediaAssignment(tmp_path / "missing.mp3", ":iPod_Control:Music:F00:BBBB.mp3", "iPod_Control/Music/F00/BBBB.mp3"),
    ]
    with pytest.raises(Exception):
        copy_media(mount, asg)
    assert not (mount / "iPod_Control/Music/F00/AAAA.mp3").exists()


def test_copy_media_no_sobrescribe_existente(tmp_path):
    mount = _fake_ipod(tmp_path)
    existing = mount / "iPod_Control/Music/F00/AAAA.mp3"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"ORIGINAL")
    src = tmp_path / "new.mp3"
    src.write_bytes(b"NEW")
    asg = [MediaAssignment(src, ":iPod_Control:Music:F00:AAAA.mp3", "iPod_Control/Music/F00/AAAA.mp3")]
    with pytest.raises(Exception):
        copy_media(mount, asg)
    assert existing.read_bytes() == b"ORIGINAL"


def test_copy_media_rechaza_destino_fuera_de_ipod_control(tmp_path):
    mount = _fake_ipod(tmp_path)
    src = tmp_path / "x.mp3"
    src.write_bytes(b"x")
    asg = [MediaAssignment(src, ":Escape:x.mp3", "../escape.mp3")]
    with pytest.raises(Exception):
        copy_media(mount, asg)
    assert not (tmp_path / "escape.mp3").exists()
