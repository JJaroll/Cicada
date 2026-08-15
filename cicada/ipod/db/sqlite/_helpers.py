"""Shared helpers for SQLiteDB_Writer modules.

Centralises utilities that were previously duplicated across
library_writer, locations_writer, dynamic_writer, extras_writer,
and genius_writer.
"""

import os
import sqlite3

__all__ = [
    "CORE_DATA_EPOCH",
    "SQLITE_INT_MASK",
    "unix_to_coredata",
    "coredata_to_unix",
    "s64",
    "u64",
    "open_db",
]

# ── Timestamp helpers ──────────────────────────────────────────────────
# SQLite databases use Core Data timestamps: seconds since 2001-01-01 UTC
# (the Cocoa/Core Foundation reference date).
CORE_DATA_EPOCH = 978307200  # Unix timestamp of 2001-01-01 00:00:00 UTC

#: Máscara para normalizar enteros de 64 bits a su representación sin signo (uint64).
SQLITE_INT_MASK = 0xFFFFFFFFFFFFFFFF


def unix_to_coredata(unix_ts: int) -> int:
    """Convert Unix timestamp to Core Data timestamp.

    Args:
        unix_ts: Unix timestamp (seconds since 1970-01-01)
    Returns:
        Core Data timestamp (seconds since 2001-01-01 UTC).
        Returns 0 if input is 0.
    """
    if unix_ts == 0:
        return 0
    return unix_ts - CORE_DATA_EPOCH


def coredata_to_unix(coredata_ts: int) -> int:
    """Convert Core Data timestamp (seconds since 2001-01-01 UTC) to Unix timestamp (1970).

    Args:
        coredata_ts: Core Data timestamp.
    Returns:
        Unix timestamp (seconds since 1970-01-01).
        Returns 0 if input is 0.
    """
    if coredata_ts == 0:
        return 0
    return coredata_ts + CORE_DATA_EPOCH


def s64(val: int) -> int:
    """Convert unsigned 64-bit int to signed for SQLite INTEGER storage.

    SQLite INTEGER is signed 64-bit (max 2^63-1).  iPod db_ids and PIDs
    are unsigned 64-bit values that may exceed this limit.
    """
    if val >= (1 << 63):
        return val - (1 << 64)
    return val


def u64(val: int) -> int:
    """Convierte un entero de 64 bits con signo (SQLite INTEGER) a sin signo (parser iTunesCDB).

    Inverso de :func:`s64`. SQLite almacena los INTEGERs como enteros con signo de 64 bits
    (rango -2^63 a 2^63-1), mientras que el parser de iTunesCDB los lee como enteros sin
    signo de 64 bits (uint64, rango 0 a 2^64-1).

    Toda comparación de dbids / PIDs entre capas DEBE normalizarse con esta función;
    sin esto, el MISMO id (cuyo bit más significativo es 1) aparece como un número negativo
    en SQLite y como un número positivo grande en iTunesCDB, produciendo un "los dbids no cuadran"
    imposible de depurar.
    """
    return val & SQLITE_INT_MASK


def open_db(path: str, extra_pragmas: list[str] | None = None) -> tuple[sqlite3.Connection, sqlite3.Cursor]:
    """Create a fresh SQLite database at *path*.

    Deletes any existing file, opens a new connection with performance
    PRAGMAs (journal_mode=OFF, synchronous=OFF), and returns (conn, cursor).

    Args:
        path: Output file path.
        extra_pragmas: Additional PRAGMA statements to execute
                       (e.g. ``["encoding='UTF-8'"]``).
    """
    if os.path.exists(path):
        os.remove(path)

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    for pragma in extra_pragmas or []:
        conn.execute(f"PRAGMA {pragma}")

    return conn, conn.cursor()
