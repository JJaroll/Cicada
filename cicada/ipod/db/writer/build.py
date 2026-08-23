"""Construcción del iTunesCDB — código propio de Cicada (produce BYTES).

Reimplementa la entrada de escritura de iOpenPod (`write_itunesdb`), que estaba
enredada con el stack de escritura-al-dispositivo (path_safety, storage_safety,
write_readiness, su write_guard). Aquí solo se producen bytes:

1. `write_mhbd` (builder puro vendorizado) → iTunesDB descomprimido.
2. Compresión zlib a iTunesCDB (§0.1/§0.3): cabecera + `zlib.compress(payload, 1)`,
   `total_length` parcheado, `unk_0xA8 = 1`.
3. Firma **sobre el comprimido** (§0.3): HASHAB para Nano 6G/7G.

La instalación al volumen es responsabilidad del coordinador (Etapa 2c) vía
`safe_write`. Aquí no se toca disco.
"""
from __future__ import annotations

import struct
import zlib
from typing import Optional

from cicada.ipod.db.shared.device_time import (
    DeviceTimeContext,
    use_device_time_context,
)
from cicada.ipod.device.capabilities import DeviceCapabilities
from cicada.ipod.device.checksum import ChecksumType

from .hashab import write_hashab
from .mhbd_writer import write_mhbd
from .mhit_writer import TrackInfo
from .mhyp_writer import PlaylistInfo

__all__ = ["build_itunescdb"]


def build_itunescdb(
    tracks: list[TrackInfo],
    *,
    firewire_id: bytes,
    checksum: ChecksumType,
    capabilities: Optional[DeviceCapabilities] = None,
    playlists_type2: Optional[list[PlaylistInfo]] = None,
    playlists_type5: Optional[list[PlaylistInfo]] = None,
    preserved_mhsd_blobs: Optional[list[bytes]] = None,
    db_id: Optional[int] = None,
    master_playlist_name: str = "iPod",
    time_context: Optional[DeviceTimeContext] = None,
) -> bytes:
    """Construye los bytes del iTunesCDB (comprimido y firmado). No escribe disco.

    ``time_context``: contexto horario del dispositivo (el MISMO con el que se leyó
    la base). Imprescindible para que las fechas (``date_added``/``last_modified``,
    guardadas como segundos-mac en hora local) no se desplacen por el offset de la
    zona. Sin él, las fechas se reconvierten con UTC y cambian.
    """
    if not firewire_id or len(firewire_id) < 8:
        raise ValueError("firewire_id de 8+ bytes requerido para firmar")

    ctx = time_context or DeviceTimeContext.utc()
    with use_device_time_context(ctx):
        raw = write_mhbd(
            tracks,
            db_id=db_id,
            playlists_type2=playlists_type2,
            playlists_type5=playlists_type5,
            preserved_mhsd_blobs=preserved_mhsd_blobs,
            capabilities=capabilities,
            master_playlist_name=master_playlist_name,
        )

    hdr_len = struct.unpack_from("<I", raw, 4)[0]
    payload = bytes(raw[hdr_len:])
    compressed = zlib.compress(payload, 1)
    cdb = bytearray(raw[:hdr_len]) + bytearray(compressed)
    struct.pack_into("<I", cdb, 8, len(cdb))
    struct.pack_into("<H", cdb, 0xA8, 1)

    if checksum is ChecksumType.HASHAB:
        write_hashab(cdb, firewire_id)
    elif checksum is ChecksumType.HASH58:
        from .hash58 import write_hash58
        write_hash58(cdb, firewire_id)
    elif checksum is ChecksumType.HASH72:
        raise NotImplementedError(
            "HASH72 (Nano 5G) requiere un HashInfo extraído de iTunes; no soportado en v1")
    else:
        raise ValueError(f"Esquema de checksum no soportado para escritura: {checksum}")

    return bytes(cdb)
