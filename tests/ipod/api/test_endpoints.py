"""Tests de los endpoints iPod de lectura de la UI (scan / tracks / playlists).

Estos endpoints se consolidaron en el router canónico ``cicada.ipod.api`` (antes
estaban duplicados en ``core/main.py``). Se prueban las funciones del router
directamente, presentando el fixture como iPod montado. Sin dispositivo real.
"""
import shutil
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

from cicada.ipod import api
from cicada.ipod.device import write_guard as wg

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "nano7g-iopenpod"
skip_no_fixture = pytest.mark.skipif(
    not (FIXTURE / "iTunes" / "iTunesCDB").exists() or sys.platform == "win32",
    reason="fixture no presente (o symlinks no POSIX)",
)


@pytest.fixture
def ipod_mount(tmp_path, monkeypatch):
    m = tmp_path / "IPOD"
    m.mkdir()
    (m / "iPod_Control").symlink_to(FIXTURE)
    monkeypatch.setattr(wg, "_candidate_mounts", lambda: [m])
    return m


@skip_no_fixture
def test_scan_ready(ipod_mount):
    r = api.scan_ipods()
    assert r["state"] == "ready"
    assert len(r["ipods"]) == 1
    ip = r["ipods"][0]
    assert ip["model_family"] == "iPod Nano"
    assert ip["generation"] == "7th Gen"
    assert ip["capacity"] == "16GB"
    assert ip["checksum"] == "HASHAB"


def test_scan_no_device(monkeypatch):
    monkeypatch.setattr(wg, "_candidate_mounts", lambda: [])
    r = api.scan_ipods()
    assert r["state"] == "no_device"
    assert r["ipods"] == []


def test_scan_no_ipod_control(tmp_path, monkeypatch):
    vol = tmp_path / "IPOD"
    vol.mkdir()
    monkeypatch.setattr(wg, "_candidate_mounts", lambda: [vol])
    r = api.scan_ipods()
    assert r["state"] == "no_ipod_control"
    assert r["ipods"] == []
    assert len(r["volumes_without_control"]) == 1


@skip_no_fixture
def test_tracks(ipod_mount):
    r = api.get_ipod_tracks()
    assert r.tracks_count == 25
    assert r.tracks[0].artist == "Lady Gaga"
    assert r.tracks[0].title == "LoveDrug (Apple Music Live)"
    assert r.tracks[0].filetype == "MP3"


@skip_no_fixture
def test_playlists(ipod_mount):
    r = api.ipod_playlists()
    assert r["count"] == 3
    titles = [p["title"] for p in r["playlists"]]
    assert "iPod" in titles
    master = next(p for p in r["playlists"] if p["title"] == "iPod")
    assert master["is_master"] is True
    assert master["count"] == 25


def test_tracks_sin_ipod_lanza_error(monkeypatch):
    monkeypatch.setattr(wg, "_candidate_mounts", lambda: [])
    with pytest.raises(HTTPException) as exc:
        api.get_ipod_tracks()
    assert exc.value.status_code == 404


@skip_no_fixture
def test_lectura_revalida_montaje(ipod_mount):
    scan = api.scan_ipods()
    assert scan["state"] == "ready"
    shutil.rmtree(ipod_mount)
    with pytest.raises(HTTPException) as exc:
        api.get_ipod_tracks()
    assert exc.value.status_code == 404
