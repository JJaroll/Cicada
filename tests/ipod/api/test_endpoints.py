"""Tests de los endpoints iPod de la API (Fase 1, solo lectura).

Monkeypatchea _candidate_mounts para presentar el fixture como iPod montado.
Sin dispositivo real. Verifica los 3 estados y el listado.
"""
import asyncio
import sys
from pathlib import Path

import pytest

from cicada.ipod.device import write_guard as wg
from cicada.core import main as app_main

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


def _run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# scan — 3 estados
# --------------------------------------------------------------------------- #
@skip_no_fixture
def test_scan_ready(ipod_mount):
    r = _run(app_main.scan_ipods())
    assert r["state"] == "ready"
    assert len(r["ipods"]) == 1
    ip = r["ipods"][0]
    assert ip["model_family"] == "iPod Nano"
    assert ip["generation"] == "7th Gen"
    assert ip["capacity"] == "16GB"
    assert ip["checksum"] == "HASHAB"


def test_scan_no_device(monkeypatch):
    monkeypatch.setattr(wg, "_candidate_mounts", lambda: [])
    r = _run(app_main.scan_ipods())
    assert r["state"] == "no_device"
    assert r["ipods"] == []


def test_scan_no_ipod_control(tmp_path, monkeypatch):
    # Volumen que parece iPod (nombre) pero sin iPod_Control.
    vol = tmp_path / "IPOD"
    vol.mkdir()
    monkeypatch.setattr(wg, "_candidate_mounts", lambda: [vol])
    r = _run(app_main.scan_ipods())
    assert r["state"] == "no_ipod_control"
    assert r["ipods"] == []
    assert len(r["volumes_without_control"]) == 1


# --------------------------------------------------------------------------- #
# tracks / playlists
# --------------------------------------------------------------------------- #
@skip_no_fixture
def test_tracks(ipod_mount):
    r = _run(app_main.ipod_tracks())
    assert r["count"] == 25
    assert r["tracks"][0]["artist"] == "Lady Gaga"
    assert r["tracks"][0]["title"] == "LoveDrug (Apple Music Live)"
    assert r["tracks"][0]["filetype"] == "MP3"


@skip_no_fixture
def test_playlists(ipod_mount):
    r = _run(app_main.ipod_playlists())
    assert r["count"] == 3
    titles = [p["title"] for p in r["playlists"]]
    assert "iPod" in titles
    master = next(p for p in r["playlists"] if p["title"] == "iPod")
    assert master["is_master"] is True
    assert master["count"] == 25


def test_tracks_sin_ipod_lanza_503(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(wg, "_candidate_mounts", lambda: [])
    with pytest.raises(HTTPException) as exc:
        _run(app_main.ipod_tracks())
    assert exc.value.status_code == 503


@skip_no_fixture
def test_lectura_revalida_montaje(ipod_mount, monkeypatch):
    # Si el iPod se desmonta entre el scan y la lectura -> 503 (revalidación).
    from fastapi import HTTPException
    import shutil
    # discover_ipods encuentra el mount; pero resolve_mount revalida y ya no está.
    scan = _run(app_main.scan_ipods())
    assert scan["state"] == "ready"
    shutil.rmtree(ipod_mount)                       # se desmonta
    with pytest.raises(HTTPException) as exc:
        _run(app_main.ipod_tracks())
    assert exc.value.status_code == 503
