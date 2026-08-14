"""Tests unitarios para helpers de SQLite (_helpers.py).

Verifica la normalización u64 / s64 de dbids/PIDs para evitar discrepancias
entre los INTEGERs con signo de SQLite y los uint64 sin signo del parser de iTunesCDB.
"""
from __future__ import annotations

import pytest

from cicada.ipod.db.sqlite._helpers import (
    CORE_DATA_EPOCH,
    SQLITE_INT_MASK,
    s64,
    u64,
    unix_to_coredata,
)


def test_u64_positive_integers():
    """Valores positivos dentro del rango signed 63-bit se conservan idénticos."""
    assert u64(0) == 0
    assert u64(1) == 1
    assert u64(42) == 42
    assert u64(1_000_000) == 1_000_000
    assert u64((1 << 63) - 1) == 0x7FFFFFFFFFFFFFFF


def test_u64_negative_integers():
    """Valores negativos (bit más significativo en 1) se proyectan al rango uint64."""
    assert u64(-1) == 0xFFFFFFFFFFFFFFFF
    assert u64(-2) == 0xFFFFFFFFFFFFFFFE
    assert u64(-(1 << 63)) == 0x8000000000000000


def test_s64_u64_roundtrip_symmetry():
    """Para cualquier uint64 X, u64(s64(X)) == X. Para cualquier int64 Y, s64(u64(Y)) == Y."""
    test_uint64_values = [
        0,
        1,
        0x7FFFFFFFFFFFFFFF,
        0x8000000000000000,
        0x8000000000000001,
        0xFFFFFFFFFFFFFFFE,
        0xFFFFFFFFFFFFFFFF,
        0x000A27002484DDFB,
        0xD5716E8E890BDCE4,
    ]
    for val in test_uint64_values:
        signed = s64(val)
        restored = u64(signed)
        assert restored == val, f"Fallo de round-trip uint64: {val} -> {signed} -> {restored}"

    test_int64_values = [
        0,
        1,
        (1 << 63) - 1,
        -(1 << 63),
        -(1 << 63) + 1,
        -1,
        -42,
    ]
    for val in test_int64_values:
        unsigned = u64(val)
        restored = s64(unsigned)
        assert restored == val, f"Fallo de round-trip int64: {val} -> {unsigned} -> {restored}"


def test_mask_constant():
    """SQLITE_INT_MASK debe ser exactamente 0xFFFFFFFFFFFFFFFF (64 bits en 1)."""
    assert SQLITE_INT_MASK == (1 << 64) - 1
    assert SQLITE_INT_MASK == 0xFFFFFFFFFFFFFFFF


def test_unix_to_coredata():
    """unix_to_coredata convierte correctamente y respeta el centinela 0."""
    assert unix_to_coredata(0) == 0
    assert unix_to_coredata(CORE_DATA_EPOCH) == 0
    assert unix_to_coredata(CORE_DATA_EPOCH + 100) == 100
