"""Tests reales de device_time (vendorizado de iOpenPod).

El módulo con más riesgo de bug sutil: segundos desde 1904-01-01 en la hora
local del dispositivo <-> segundos Unix UTC. Se cubre conversión en ambas
direcciones con fecha conocida, round-trip, y comportamiento con DST usando
America/Santiago (hemisferio sur: verano DST -03, invierno -04).
"""
from datetime import UTC, datetime

import pytest

from cicada.ipod.db.shared.device_time import (
    MAC_EPOCH_OFFSET,
    DeviceTimeContext,
    MacTimestampOutOfRangeError,
)

try:
    DeviceTimeContext.from_timezone_name("America/Santiago")
    _HAS_SANTIAGO = True
except Exception:
    _HAS_SANTIAGO = False

requires_santiago = pytest.mark.skipif(
    not _HAS_SANTIAGO, reason="America/Santiago no disponible (falta tzdata)"
)


def test_fecha_conocida_ambas_direcciones_utc():
    ctx = DeviceTimeContext.utc()
    dt = datetime(2010, 6, 15, 12, 0, 0, tzinfo=UTC)
    unix = int(dt.timestamp())
    mac_esperado = unix + MAC_EPOCH_OFFSET
    assert ctx.unix_to_mac(unix) == mac_esperado
    assert ctx.mac_to_unix(mac_esperado) == unix


def test_epoca_mac_1904_es_offset_conocido():
    assert MAC_EPOCH_OFFSET == 2_082_844_800
    ctx = DeviceTimeContext.utc()
    assert ctx.unix_to_mac(1) == MAC_EPOCH_OFFSET + 1
    assert ctx.mac_to_unix(MAC_EPOCH_OFFSET + 1) == 1


@pytest.mark.parametrize("unix", [1, 1000, 1168300800, 1262304000, 1600000000])
def test_round_trip_utc(unix):
    ctx = DeviceTimeContext.utc()
    assert ctx.mac_to_unix(ctx.unix_to_mac(unix)) == unix


def test_valores_no_positivos_devuelven_cero():
    ctx = DeviceTimeContext.utc()
    assert ctx.unix_to_mac(0) == 0
    assert ctx.unix_to_mac(-5) == 0
    assert ctx.mac_to_unix(0) == 0
    assert ctx.mac_to_unix(-1) == 0


def test_fuera_de_rango_u32_lanza():
    ctx = DeviceTimeContext.utc()
    unix_2100 = int(datetime(2100, 1, 1, tzinfo=UTC).timestamp())
    with pytest.raises(MacTimestampOutOfRangeError):
        ctx.unix_to_mac(unix_2100)


def test_offset_fijo_desplaza_pared():
    ctx = DeviceTimeContext.fixed_offset(-4 * 3600)
    ctx_utc = DeviceTimeContext.utc()
    unix = int(datetime(2015, 3, 10, 15, 0, tzinfo=UTC).timestamp())
    assert ctx.unix_to_mac(unix) == ctx_utc.unix_to_mac(unix) - 4 * 3600
    assert ctx.mac_to_unix(ctx.unix_to_mac(unix)) == unix


@requires_santiago
def test_santiago_offset_verano_vs_invierno():
    ctx = DeviceTimeContext.from_timezone_name("America/Santiago")
    verano = int(datetime(2024, 1, 15, 12, 0, tzinfo=UTC).timestamp())
    invierno = int(datetime(2024, 7, 15, 12, 0, tzinfo=UTC).timestamp())
    assert ctx.offset_at_unix(verano) == -3 * 3600
    assert ctx.offset_at_unix(invierno) == -4 * 3600


@requires_santiago
def test_santiago_mac_refleja_offset_dst():
    ctx = DeviceTimeContext.from_timezone_name("America/Santiago")
    ctx_utc = DeviceTimeContext.utc()
    verano = int(datetime(2024, 1, 15, 12, 0, tzinfo=UTC).timestamp())
    invierno = int(datetime(2024, 7, 15, 12, 0, tzinfo=UTC).timestamp())
    assert ctx.unix_to_mac(verano) == ctx_utc.unix_to_mac(verano) - 3 * 3600
    assert ctx.unix_to_mac(invierno) == ctx_utc.unix_to_mac(invierno) - 4 * 3600


@requires_santiago
@pytest.mark.parametrize("mes_dia", [(1, 15), (7, 15), (11, 20)])
def test_santiago_round_trip_fuera_de_transicion(mes_dia):
    ctx = DeviceTimeContext.from_timezone_name("America/Santiago")
    mes, dia = mes_dia
    unix = int(datetime(2024, mes, dia, 12, 0, tzinfo=UTC).timestamp())
    assert ctx.mac_to_unix(ctx.unix_to_mac(unix)) == unix


def _find_fallback_transition(ctx, year):
    """Instante Unix del retroceso DST (offset -3h -> -4h) del año, o None."""
    start = int(datetime(year, 1, 1, tzinfo=UTC).timestamp())
    end = int(datetime(year + 1, 1, 1, tzinfo=UTC).timestamp())
    prev_off = ctx.offset_at_unix(start)
    hour_boundary = None
    t = start + 3600
    while t < end:
        off = ctx.offset_at_unix(t)
        if prev_off == -3 * 3600 and off == -4 * 3600:
            hour_boundary = t
            break
        prev_off = off
        t += 3600
    if hour_boundary is None:
        return None
    lo = hour_boundary - 3600
    for s in range(lo, hour_boundary + 1):
        if ctx.offset_at_unix(s) == -4 * 3600:
            return s
    return None


@requires_santiago
def test_santiago_retroceso_dst_ambiguedad_de_pared():
    """En el retroceso, dos instantes UTC a 1h comparten hora de pared.

    Como el iPod guarda la hora de PARED (no UTC), ambos colapsan al mismo mac:
    es la limitación conocida del formato. mac_to_unix recupera el primero.
    """
    ctx = DeviceTimeContext.from_timezone_name("America/Santiago")
    transicion = _find_fallback_transition(ctx, 2024)
    assert transicion is not None, "no se encontró el retroceso DST de Santiago 2024"

    a = transicion - 1
    b = a + 3600
    assert ctx.offset_at_unix(a) == -3 * 3600
    assert ctx.offset_at_unix(b) == -4 * 3600

    assert ctx.unix_to_mac(a) == ctx.unix_to_mac(b)
    assert ctx.mac_to_unix(ctx.unix_to_mac(a)) == a
    assert ctx.mac_to_unix(ctx.unix_to_mac(b)) == a


@requires_santiago
def test_santiago_adelanto_dst_round_trip_se_conserva():
    """En el adelanto (primavera) no hay ambigüedad: el round-trip se conserva
    a ambos lados de la transición."""
    ctx = DeviceTimeContext.from_timezone_name("America/Santiago")
    start = int(datetime(2024, 1, 1, tzinfo=UTC).timestamp())
    end = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp())
    prev = ctx.offset_at_unix(start)
    t = start + 3600
    salto = None
    while t < end:
        off = ctx.offset_at_unix(t)
        if prev == -4 * 3600 and off == -3 * 3600:
            salto = t
            break
        prev = off
        t += 3600
    assert salto is not None
    antes = salto - 7200
    despues = salto + 7200
    assert ctx.mac_to_unix(ctx.unix_to_mac(antes)) == antes
    assert ctx.mac_to_unix(ctx.unix_to_mac(despues)) == despues
