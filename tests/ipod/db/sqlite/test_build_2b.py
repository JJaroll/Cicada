"""Etapa 2b — escritura de las bases SQLite (`iTunes Library.itlp/`) en staging.

Aceptación (requisitos del usuario):
1. **Comparación campo por campo** de los 25 originales entre las `.itdb` del
   fixture y las que producimos — incluido `Dynamic.item_stats.date_played`.
   Si algo cambió sin pedirlo, el writer pierde/altera datos.
2. **Coherencia entre capas, detectable**: los dbids se leen de las DOS salidas
   por separado (parser del iTunesCDB por un lado, sqlite3 por otro) y se comparan
   los conjuntos. Un test negativo demuestra que la verificación FALLA si divergen.
3. **Vigilancia época Cocoa**: `date_played` de una pista nunca reproducida debe
   ser 0 (no el centinela 2001 desplazado por la zona). Regresión del fix.
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

wasmtime = pytest.importorskip("wasmtime", reason="wasmtime no instalado")

from cicada.ipod.db.parser import load_ipod_library
from cicada.ipod.db.shared.device_time import read_device_time_context
from cicada.ipod.db.sqlite.build import build_sqlite_databases
from cicada.ipod.db.writer._track_conversion import track_dict_to_info
from cicada.ipod.db.writer.build import build_itunescdb
from cicada.ipod.db.writer.mhit_writer import TrackInfo
from cicada.ipod.device.capabilities import capabilities_for_family_gen
from cicada.ipod.device.checksum import ChecksumType

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "nano7g-iopenpod"
CDB = FIXTURE / "iTunes" / "iTunesCDB"
ITLP = FIXTURE / "iTunes" / "iTunes Library.itlp"
GUID = bytes.fromhex("000A27002484DDFB")

skip_no_fixture = pytest.mark.skipif(
    not CDB.exists() or not ITLP.exists() or sys.platform == "win32",
    reason="fixture no presente (o symlinks no POSIX)",
)


def _u64(v: int) -> int:
    """SQLite guarda INTEGER con signo; el parser del iTunesCDB lee sin signo.
    Normalizamos a 64-bit sin signo para comparar el MISMO valor entre capas."""
    return v & 0xFFFFFFFFFFFFFFFF


def _rows(db_path: Path, table: str, pid_col: str) -> dict:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = {_u64(r[pid_col]): dict(r) for r in con.execute(f"SELECT * FROM {table}")}
    finally:
        con.close()
    return rows


# --------------------------------------------------------------------------- #
@pytest.fixture
def built(tmp_path):
    """Construye iTunesCDB (2a) + SQLite (2b) desde los 25 tracks del fixture,
    con el MISMO contexto horario del dispositivo. Devuelve rutas y bytes."""
    src = tmp_path / "src_IPOD"
    src.mkdir()
    (src / "iPod_Control").symlink_to(FIXTURE)
    orig = load_ipod_library(
        str(src / "iPod_Control" / "iTunes" / "iTunesCDB"), mount=str(src)
    )["mhlt"]
    ctx = read_device_time_context(str(src))
    tis = [track_dict_to_info(t) for t in orig]
    caps = capabilities_for_family_gen("iPod Nano", "7th Gen")

    itlp = tmp_path / "itlp"
    build_sqlite_databases(
        itlp, tis, firewire_id=GUID, checksum=ChecksumType.HASHAB,
        capabilities=caps, time_context=ctx,
    )
    cdb = build_itunescdb(
        tis, firewire_id=GUID, checksum=ChecksumType.HASHAB,
        capabilities=caps, time_context=ctx,
    )
    return {"orig": orig, "itlp": itlp, "cdb": cdb, "tmp": tmp_path}


# --------------------------------------------------------------------------- #
# 0. Produce los 6 archivos del itlp/
# --------------------------------------------------------------------------- #
@skip_no_fixture
def test_produce_los_seis_archivos(built):
    nombres = sorted(p.name for p in built["itlp"].iterdir())
    assert nombres == [
        "Dynamic.itdb", "Extras.itdb", "Genius.itdb",
        "Library.itdb", "Locations.itdb", "Locations.itdb.cbk",
    ]
    # Los .itdb son SQLite reales (validador independiente).
    for f in ("Library.itdb", "Locations.itdb", "Dynamic.itdb"):
        assert (built["itlp"] / f).read_bytes()[:15] == b"SQLite format 3"


# --------------------------------------------------------------------------- #
# 1. Comparación campo por campo — Library.item + Dynamic.item_stats
# --------------------------------------------------------------------------- #
_LIB_FIELDS = [
    "title", "artist", "album", "album_artist", "genre_id",
    "total_time_ms", "track_number", "track_count", "disc_number",
    "year", "date_modified", "media_kind",
]
_DYN_FIELDS = [
    "has_been_played", "date_played", "play_count_user",
    "date_skipped", "skip_count_user", "user_rating",
]


@skip_no_fixture
def test_library_item_identico_campo_por_campo(built):
    fix = _rows(ITLP / "Library.itdb", "item", "pid")
    our = _rows(built["itlp"] / "Library.itdb", "item", "pid")
    assert set(fix) == set(our), "los pids de Library.item difieren del fixture"
    problemas = []
    for pid in fix:
        for f in _LIB_FIELDS:
            if fix[pid].get(f) != our[pid].get(f):
                problemas.append(f"item[{pid:#x}].{f}: {fix[pid].get(f)!r} -> {our[pid].get(f)!r}")
    assert not problemas, "Library.itdb alterado:\n" + "\n".join(problemas[:20])


@skip_no_fixture
def test_dynamic_item_stats_identico_incluido_date_played(built):
    fix = _rows(ITLP / "Dynamic.itdb", "item_stats", "item_pid")
    our = _rows(built["itlp"] / "Dynamic.itdb", "item_stats", "item_pid")
    assert set(fix) == set(our), "los item_pid de Dynamic difieren del fixture"
    problemas = []
    for pid in fix:
        for f in _DYN_FIELDS:
            if fix[pid].get(f) != our[pid].get(f):
                problemas.append(f"item_stats[{pid:#x}].{f}: {fix[pid].get(f)!r} -> {our[pid].get(f)!r}")
    assert not problemas, "Dynamic.itdb alterado:\n" + "\n".join(problemas[:20])


# --------------------------------------------------------------------------- #
# 2. Coherencia entre capas — DETECTABLE (dbids leídos por separado)
# --------------------------------------------------------------------------- #
def _cdb_dbids(cdb_bytes: bytes, tmp: Path, tag: str) -> set:
    """dbids leídos SÓLO por el parser del iTunesCDB (sin signo)."""
    stage = tmp / f"cdb_{tag}" / "iPod_Control" / "iTunes"
    stage.mkdir(parents=True)
    (stage / "iTunesCDB").write_bytes(cdb_bytes)
    tracks = load_ipod_library(
        str(stage / "iTunesCDB"), mount=str(tmp / f"cdb_{tag}")
    )["mhlt"]
    return {_u64(t["db_track_id"]) for t in tracks}


def _sqlite_dbids(itlp: Path) -> set:
    """dbids leídos SÓLO por sqlite3 (validador independiente), normalizados."""
    return set(_rows(itlp / "Library.itdb", "item", "pid").keys())


@skip_no_fixture
def test_coherencia_dbids_entre_capas(built):
    # Las dos salidas se leen por caminos independientes y se comparan.
    cdb_ids = _cdb_dbids(built["cdb"], built["tmp"], "ok")
    sql_ids = _sqlite_dbids(built["itlp"])
    assert len(cdb_ids) == len(sql_ids) == 25
    assert cdb_ids == sql_ids, (
        "divergencia entre capas: "
        f"sólo CDB={sorted(cdb_ids - sql_ids)[:3]}, "
        f"sólo SQLite={sorted(sql_ids - cdb_ids)[:3]}"
    )


@skip_no_fixture
def test_la_verificacion_de_coherencia_detecta_divergencia(built, tmp_path):
    """Test negativo: si el iTunesCDB y el SQLite se construyen con conjuntos de
    tracks distintos, la comparación de dbids DEBE fallar. Garantiza que el
    invariante del test anterior no es una tautología."""
    ctx = read_device_time_context(str(built["tmp"] / "src_IPOD"))
    tis = [track_dict_to_info(t) for t in built["orig"]]
    caps = capabilities_for_family_gen("iPod Nano", "7th Gen")

    # SQLite con un track EXTRA que el iTunesCDB no tiene.
    tis_mas = tis + [TrackInfo(
        title="Intruso", location=":iPod_Control:Music:F00:ZZZZ.mp3",
        artist="X", filetype="mp3", length=1000, size=1000,
    )]
    itlp2 = tmp_path / "itlp_divergente"
    build_sqlite_databases(
        itlp2, tis_mas, firewire_id=GUID, checksum=ChecksumType.HASHAB,
        capabilities=caps, time_context=ctx,
    )
    cdb_ids = _cdb_dbids(built["cdb"], built["tmp"], "orig")   # 25
    sql_ids = _sqlite_dbids(itlp2)                             # 26
    assert cdb_ids != sql_ids, "la verificación NO detectó la divergencia (26 vs 25)"
    assert len(sql_ids - cdb_ids) == 1


# --------------------------------------------------------------------------- #
# 3. Vigilancia época Cocoa — nunca reproducida ⇒ date_played 0 (regresión)
# --------------------------------------------------------------------------- #
@skip_no_fixture
def test_nunca_reproducida_date_played_cero(tmp_path):
    """Una pista con play_count=0 no lleva fecha de reproducción. Sin el fix,
    el centinela 2001-01-01 se reconvierte a Cocoa y se desplaza por la zona
    (aparecía -14400 = -4h). El formato de fechas ya nos mordió en 2a."""
    ctx = read_device_time_context(str(tmp_path))  # UTC por defecto (sin device)
    t = TrackInfo(
        title="Sin reproducir", location=":iPod_Control:Music:F00:AAAA.mp3",
        artist="X", filetype="mp3", length=1000, size=1000,
        play_count=0, skip_count=0,
    )
    # Un centinela 2001-01-01 en local, como el que trae el iTunesCDB real.
    t.last_played = 978292800
    t.last_skipped = 978292800
    itlp = tmp_path / "itlp"
    build_sqlite_databases(
        itlp, [t], firewire_id=GUID, checksum=ChecksumType.HASHAB,
        time_context=ctx,
    )
    stats = _rows(itlp / "Dynamic.itdb", "item_stats", "item_pid")
    (row,) = stats.values()
    assert row["has_been_played"] == 0
    assert row["date_played"] == 0, f"date_played desplazado: {row['date_played']}"
    assert row["date_skipped"] == 0, f"date_skipped desplazado: {row['date_skipped']}"


@skip_no_fixture
def test_reproducida_conserva_fecha(tmp_path):
    """Contraparte: una pista SÍ reproducida conserva su date_played (Cocoa)."""
    ctx = read_device_time_context(str(tmp_path))
    played_unix = 1_700_000_000  # 2023-11-14, instante real
    t = TrackInfo(
        title="Reproducida", location=":iPod_Control:Music:F00:BBBB.mp3",
        artist="X", filetype="mp3", length=1000, size=1000, play_count=3,
    )
    t.last_played = played_unix
    itlp = tmp_path / "itlp"
    build_sqlite_databases(
        itlp, [t], firewire_id=GUID, checksum=ChecksumType.HASHAB,
        time_context=ctx,
    )
    (row,) = _rows(itlp / "Dynamic.itdb", "item_stats", "item_pid").values()
    assert row["has_been_played"] == 1
    assert row["date_played"] == played_unix - 978307200  # unix→CoreData
