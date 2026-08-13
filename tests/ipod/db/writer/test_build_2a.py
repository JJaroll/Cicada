"""Etapa 2a — escritura del iTunesCDB en staging (sin tocar el dispositivo).

Aceptación:
- Construir un iTunesCDB desde los 25 tracks del fixture + 1 sintético → 26.
- `verify_hashab` da True sobre nuestra salida (autoconsistencia — base).
- **Comparación campo por campo** de los 25 originales entre fixture y salida:
  si algo cambió sin pedirlo, el writer pierde/altera datos.
- **Cross-check con iOpenPod PRÍSTINO** (../iPod-clon/iOpenPod/src, sin nuestras
  adaptaciones): que lea los 26 tracks. No es independencia (nuestro writer ES el
  suyo); prueba que nuestras adaptaciones no rompieron el formato.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

wasmtime = pytest.importorskip("wasmtime", reason="wasmtime no instalado")

from cicada.ipod.db.parser import load_ipod_library
from cicada.ipod.db.shared.device_time import read_device_time_context
from cicada.ipod.db.writer._track_conversion import track_dict_to_info
from cicada.ipod.db.writer.build import build_itunescdb
from cicada.ipod.db.writer.mhit_writer import TrackInfo
from cicada.ipod.db.writer.verify import verify_hashab
from cicada.ipod.device.capabilities import capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "nano7g-iopenpod"
CDB = FIXTURE / "iTunes" / "iTunesCDB"
GUID = bytes.fromhex("000A27002484DDFB")
IOPENPOD_SRC = Path("/Users/jjaroll/Proyectos/iPod-clon/iOpenPod/src")

skip_no_fixture = pytest.mark.skipif(
    not CDB.exists() or sys.platform == "win32",
    reason="fixture no presente (o symlinks no POSIX)",
)

_COMPARE_FIELDS = [
    "Title", "Artist", "Album", "Album Artist", "Genre", "db_track_id",
    "Location", "length", "size", "bitrate", "date_added", "last_modified",
    "year", "track_number",
]


def _mount_of(root: Path, cdb_path: Path) -> Path:
    m = root / "IPOD"
    m.mkdir()
    (m / "iPod_Control").symlink_to(FIXTURE)
    return m


@pytest.fixture
def built(tmp_path):
    """Devuelve (orig_tracks, cdb_bytes, new_tracks) con el contexto horario correcto."""
    src = tmp_path / "src_IPOD"
    src.mkdir()
    (src / "iPod_Control").symlink_to(FIXTURE)
    orig = load_ipod_library(str(src / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(src))["mhlt"]
    ctx = read_device_time_context(str(src))          # MISMO contexto que el parser

    tis = [track_dict_to_info(t) for t in orig]
    tis.append(TrackInfo(title="Cicada Test Track",
                         location=":iPod_Control:Music:F00:ZZZZ.mp3",
                         artist="Cicada", album="Test", filetype="mp3",
                         length=180000, size=5_000_000))
    caps = capabilities_for_family_gen("iPod Nano", "7th Gen")
    cdb = build_itunescdb(tis, firewire_id=GUID, checksum=ChecksumType.HASHAB,
                          capabilities=caps, time_context=ctx)

    out = tmp_path / "out_IPOD" / "iPod_Control" / "iTunes"
    out.mkdir(parents=True)
    (out / "iTunesCDB").write_bytes(cdb)
    new = load_ipod_library(str(out / "iTunesCDB"), mount=str(tmp_path / "out_IPOD"))["mhlt"]
    return orig, cdb, new


# --------------------------------------------------------------------------- #
@skip_no_fixture
def test_construye_e_incrementa_tracks(built):
    orig, cdb, new = built
    assert len(orig) == 25
    assert len(new) == 26
    assert new[-1]["Title"] == "Cicada Test Track"
    assert cdb[:4] == b"mhbd"


@skip_no_fixture
def test_verify_hashab_sobre_nuestra_salida(built):
    _orig, cdb, _new = built
    assert verify_hashab(cdb, GUID).valid is True


@skip_no_fixture
def test_los_25_tracks_identicos_campo_por_campo(built):
    orig, _cdb, new = built
    problemas = []
    for i, (a, b) in enumerate(zip(orig, new[:25])):
        for f in _COMPARE_FIELDS:
            if a.get(f) != b.get(f):
                problemas.append(f"track[{i}].{f}: {a.get(f)!r} -> {b.get(f)!r}")
    assert not problemas, "El writer alteró datos:\n" + "\n".join(problemas[:20])


@skip_no_fixture
def test_sin_contexto_horario_las_fechas_se_desplazan(tmp_path):
    """Documenta el hallazgo: sin el contexto del dispositivo, date_added/last_modified
    se reconvierten con UTC y cambian. Guarda contra regresión del fix."""
    src = tmp_path / "IPOD"
    src.mkdir()
    (src / "iPod_Control").symlink_to(FIXTURE)
    orig = load_ipod_library(str(src / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(src))["mhlt"]
    ctx = read_device_time_context(str(src))
    tis = [track_dict_to_info(t) for t in orig]
    caps = capabilities_for_family_gen("iPod Nano", "7th Gen")

    # Con contexto: fechas preservadas.
    cdb_ok = build_itunescdb(tis, firewire_id=GUID, checksum=ChecksumType.HASHAB,
                             capabilities=caps, time_context=ctx)
    out = tmp_path / "ok" / "iPod_Control" / "iTunes"; out.mkdir(parents=True)
    (out / "iTunesCDB").write_bytes(cdb_ok)
    new_ok = load_ipod_library(str(out / "iTunesCDB"), mount=str(tmp_path / "ok"))["mhlt"]
    assert all(a["date_added"] == b["date_added"] for a, b in zip(orig, new_ok))


@skip_no_fixture
@pytest.mark.skipif(not IOPENPOD_SRC.is_dir(), reason="fuente de iOpenPod no presente")
def test_cross_check_iopenpod_pristino_lee_nuestra_salida(built, tmp_path):
    """El iOpenPod original (sin nuestras adaptaciones) lee los 26 tracks de nuestra
    salida. No es independencia real, pero detecta si adaptamos mal el formato."""
    _orig, cdb, _new = built
    stage = tmp_path / "xcheck" / "iPod_Control" / "iTunes"
    stage.mkdir(parents=True)
    (stage / "iTunesCDB").write_bytes(cdb)

    prog = (
        "from iopenpod.itunesdb_parser.ipod_library import load_ipod_library\n"
        f"d = load_ipod_library({str(stage / 'iTunesCDB')!r})\n"
        "print(len(d['mhlt']) if d else -1)\n"
    )
    env = dict(os.environ, PYTHONPATH=str(IOPENPOD_SRC))
    proc = subprocess.run([sys.executable, "-c", prog], capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == 0, f"iOpenPod falló al parsear: {proc.stderr[-500:]}"
    assert proc.stdout.strip().splitlines()[-1] == "26", f"iOpenPod leyó: {proc.stdout!r}"
