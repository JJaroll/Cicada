"""Serialización/parseo binario de ArtworkDB (MHFD/MHSD/MHLI/MHII/MHNI/MHOD)
y de las listas de archivo (MHLF/MHIF).

Adaptado de artworkdb_writer/artworkdb_chunks.py de iOpenPod (ver
docs/VENDORED.md, Paquete 7, Etapa 4c). Simplificado porque Cicada reescribe
ArtworkDB completo en cada sync (sin preservación de entradas existentes):
no hay `reference_mhfd` que fusionar ni `read_existing_artwork` con toda la
validación defensiva contra datos ajenos corruptos — `read_artworkdb` de
este módulo solo necesita releer lo que este mismo escritor acaba de
producir (verificación en staging, Etapa 4c) o, más adelante, un ArtworkDB
real del dispositivo con la misma forma.

Todo aquí produce/consume `bytes` en memoria — nada toca disco (mismo
patrón que db/writer/build.py).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional

from cicada.ipod.db.artwork.types import EncodedFormatPayload

MHFD_HEADER_SIZE = 132
MHSD_HEADER_SIZE = 96
MHLI_HEADER_SIZE = 92
MHLA_HEADER_SIZE = 92
MHLF_HEADER_SIZE = 92
MHII_HEADER_SIZE = 152
MHOD_HEADER_SIZE = 24
MHNI_HEADER_SIZE = 76
MHIF_HEADER_SIZE = 124


class ArtworkDatasetType(IntEnum):
    IMAGE_LIST = 1
    PHOTO_ALBUM_LIST = 2
    FILE_LIST = 3


class ArtworkMhodType(IntEnum):
    THUMBNAIL_IMAGE = 2
    FILE_NAME = 3


def ithmb_filename(format_id: int, index: int = 1) -> str:
    return f"F{int(format_id)}_{int(index)}.ithmb"


# ── Escritura ────────────────────────────────────────────────────────────


def _write_mhod_filename(filename: str) -> bytes:
    """MHOD tipo FILE_NAME: string UTF-16LE con prefijo ':' (convención HFS)."""
    encoded = f":{filename}".encode("utf-16-le")
    padding = (4 - (len(encoded) % 4)) % 4
    body = struct.pack("<I", len(encoded))
    body += struct.pack("<B", 2)  # encoding byte: 2 = utf-16-le
    body += b"\x00" * 3
    body += b"\x00" * 4
    body += encoded
    body += b"\x00" * padding

    total_len = MHOD_HEADER_SIZE + len(body)
    header = bytearray(MHOD_HEADER_SIZE)
    header[0:4] = b"mhod"
    struct.pack_into("<I", header, 4, MHOD_HEADER_SIZE)
    struct.pack_into("<I", header, 8, total_len)
    struct.pack_into("<H", header, 12, ArtworkMhodType.FILE_NAME)
    return bytes(header) + body


def write_mhni(format_id: int, ithmb_offset: int, payload: EncodedFormatPayload, filename: str) -> bytes:
    """Un MHNI: geometría + offset en el .ithmb + nombre de archivo hijo."""
    mhod_filename = _write_mhod_filename(filename)
    total_len = MHNI_HEADER_SIZE + len(mhod_filename)

    if payload.vpad > 0x7FFF or payload.hpad > 0x7FFF:
        raise ValueError(f"Padding demasiado grande para format {format_id}: {payload}")

    header = bytearray(MHNI_HEADER_SIZE)
    header[0:4] = b"mhni"
    struct.pack_into("<I", header, 4, MHNI_HEADER_SIZE)
    struct.pack_into("<I", header, 8, total_len)
    struct.pack_into("<I", header, 12, 1)  # child_count: solo el mhod de filename
    struct.pack_into("<I", header, 16, format_id)
    struct.pack_into("<I", header, 20, ithmb_offset)
    struct.pack_into("<I", header, 24, payload.size)
    struct.pack_into("<h", header, 28, payload.vpad)
    struct.pack_into("<h", header, 30, payload.hpad)
    struct.pack_into("<H", header, 32, payload.height)
    struct.pack_into("<H", header, 34, payload.width)
    struct.pack_into("<I", header, 40, payload.size)
    return bytes(header) + mhod_filename


def _write_mhod_container(mhod_type: int, inner: bytes) -> bytes:
    total_len = MHOD_HEADER_SIZE + len(inner)
    header = bytearray(MHOD_HEADER_SIZE)
    header[0:4] = b"mhod"
    struct.pack_into("<I", header, 4, MHOD_HEADER_SIZE)
    struct.pack_into("<I", header, 8, total_len)
    struct.pack_into("<H", header, 12, mhod_type)
    return bytes(header) + inner


def write_mhii(
    img_id: int,
    db_track_id: int,
    src_img_size: int,
    formats: Dict[int, EncodedFormatPayload],
    offsets: Dict[int, int],
    filenames: Dict[int, str],
) -> bytes:
    """Un MHII: img_id + song_id (db_track_id) + un MHOD/MHNI hijo por formato."""
    children = [
        _write_mhod_container(
            ArtworkMhodType.THUMBNAIL_IMAGE,
            write_mhni(fmt_id, offsets[fmt_id], formats[fmt_id], filenames[fmt_id]),
        )
        for fmt_id in sorted(formats.keys())
    ]
    children_data = b"".join(children)
    total_len = MHII_HEADER_SIZE + len(children_data)

    header = bytearray(MHII_HEADER_SIZE)
    header[0:4] = b"mhii"
    struct.pack_into("<I", header, 4, MHII_HEADER_SIZE)
    struct.pack_into("<I", header, 8, total_len)
    struct.pack_into("<I", header, 12, len(children))
    struct.pack_into("<I", header, 16, img_id)
    struct.pack_into("<Q", header, 20, db_track_id)
    struct.pack_into("<I", header, 48, src_img_size)
    return bytes(header) + children_data


def write_mhli(mhii_blobs: List[bytes]) -> bytes:
    header = bytearray(MHLI_HEADER_SIZE)
    header[0:4] = b"mhli"
    struct.pack_into("<I", header, 4, MHLI_HEADER_SIZE)
    struct.pack_into("<I", header, 8, len(mhii_blobs))
    return bytes(header) + b"".join(mhii_blobs)


def write_mhla() -> bytes:
    """ArtworkDB (cover art) nunca necesitó álbumes reales — siempre 0."""
    header = bytearray(MHLA_HEADER_SIZE)
    header[0:4] = b"mhla"
    struct.pack_into("<I", header, 4, MHLA_HEADER_SIZE)
    struct.pack_into("<I", header, 8, 0)
    return bytes(header)


def write_mhif(format_id: int, image_size: int) -> bytes:
    header = bytearray(MHIF_HEADER_SIZE)
    header[0:4] = b"mhif"
    struct.pack_into("<I", header, 4, MHIF_HEADER_SIZE)
    struct.pack_into("<I", header, 8, MHIF_HEADER_SIZE)
    struct.pack_into("<I", header, 16, format_id)
    struct.pack_into("<I", header, 20, image_size)
    return bytes(header)


def write_mhlf(format_ids: List[int], image_sizes: Dict[int, int]) -> bytes:
    children_data = b"".join(write_mhif(fid, image_sizes[fid]) for fid in format_ids)
    header = bytearray(MHLF_HEADER_SIZE)
    header[0:4] = b"mhlf"
    struct.pack_into("<I", header, 4, MHLF_HEADER_SIZE)
    struct.pack_into("<I", header, 8, len(format_ids))
    return bytes(header) + children_data


def write_mhsd(ds_type: int, child_data: bytes) -> bytes:
    total_len = MHSD_HEADER_SIZE + len(child_data)
    header = bytearray(MHSD_HEADER_SIZE)
    header[0:4] = b"mhsd"
    struct.pack_into("<I", header, 4, MHSD_HEADER_SIZE)
    struct.pack_into("<I", header, 8, total_len)
    struct.pack_into("<H", header, 12, ds_type)
    return bytes(header) + child_data


def write_mhfd(datasets: List[bytes], next_img_id: int) -> bytes:
    all_data = b"".join(datasets)
    total_len = MHFD_HEADER_SIZE + len(all_data)
    header = bytearray(MHFD_HEADER_SIZE)
    header[0:4] = b"mhfd"
    struct.pack_into("<I", header, 4, MHFD_HEADER_SIZE)
    struct.pack_into("<I", header, 8, total_len)
    struct.pack_into("<I", header, 16, 2)
    struct.pack_into("<I", header, 20, len(datasets))
    struct.pack_into("<I", header, 28, next_img_id)
    return bytes(header) + all_data


def build_artworkdb(
    mhii_blobs: List[bytes],
    format_ids: List[int],
    image_sizes: Dict[int, int],
    next_img_id: int,
) -> bytes:
    """Serializa el ArtworkDB completo: MHFD -> 3x MHSD (image/album/file list)."""
    ds1 = write_mhsd(ArtworkDatasetType.IMAGE_LIST, write_mhli(mhii_blobs))
    ds2 = write_mhsd(ArtworkDatasetType.PHOTO_ALBUM_LIST, write_mhla())
    ds3 = write_mhsd(ArtworkDatasetType.FILE_LIST, write_mhlf(format_ids, image_sizes))
    return write_mhfd([ds1, ds2, ds3], next_img_id)


# ── Lectura (para verificación en staging / futura Etapa 4f) ──────────────


@dataclass(frozen=True)
class ParsedFormatRef:
    format_id: int
    ithmb_offset: int
    size: int
    width: int
    height: int
    hpad: int
    vpad: int
    filename: Optional[str]


@dataclass(frozen=True)
class ParsedImageEntry:
    img_id: int
    db_track_id: int
    src_img_size: int
    formats: Dict[int, ParsedFormatRef] = field(default_factory=dict)


def _u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def _i16(data: bytes, off: int) -> int:
    return struct.unpack_from("<h", data, off)[0]


def _u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def _u64(data: bytes, off: int) -> int:
    return struct.unpack_from("<Q", data, off)[0]


def _require_tag(data: bytes, offset: int, tag: bytes) -> None:
    if data[offset:offset + 4] != tag:
        raise ValueError(f"Se esperaba {tag!r} en offset {offset}, encontrado {data[offset:offset + 4]!r}")


def _decode_mhod_filename(data: bytes, mhod_offset: int) -> Optional[str]:
    header_size = _u32(data, mhod_offset + 4)
    body_offset = mhod_offset + header_size
    string_byte_length = _u32(data, body_offset)
    raw_start = body_offset + 12
    raw = data[raw_start:raw_start + string_byte_length]
    value = raw.decode("utf-16-le", errors="replace")
    return value[1:] if value.startswith(":") else value


def _parse_mhni(data: bytes, mhni_offset: int) -> ParsedFormatRef:
    _require_tag(data, mhni_offset, b"mhni")
    header_size = _u32(data, mhni_offset + 4)
    format_id = _u32(data, mhni_offset + 16)
    ithmb_offset = _u32(data, mhni_offset + 20)
    size = _u32(data, mhni_offset + 24)
    vpad = _i16(data, mhni_offset + 28)
    hpad = _i16(data, mhni_offset + 30)
    height = _u16(data, mhni_offset + 32)
    width = _u16(data, mhni_offset + 34)

    filename = None
    child_offset = mhni_offset + header_size
    child_end = mhni_offset + _u32(data, mhni_offset + 8)
    while child_offset + MHOD_HEADER_SIZE <= child_end:
        _require_tag(data, child_offset, b"mhod")
        mhod_total = _u32(data, child_offset + 8)
        mhod_type = _u16(data, child_offset + 12)
        if mhod_type == ArtworkMhodType.FILE_NAME:
            filename = _decode_mhod_filename(data, child_offset)
        child_offset += mhod_total

    return ParsedFormatRef(format_id, ithmb_offset, size, width, height, hpad, vpad, filename)


def _parse_mhii(data: bytes, mhii_offset: int) -> ParsedImageEntry:
    _require_tag(data, mhii_offset, b"mhii")
    header_size = _u32(data, mhii_offset + 4)
    total_len = _u32(data, mhii_offset + 8)
    child_count = _u32(data, mhii_offset + 12)
    img_id = _u32(data, mhii_offset + 16)
    db_track_id = _u64(data, mhii_offset + 20)
    src_img_size = _u32(data, mhii_offset + 48)

    formats: Dict[int, ParsedFormatRef] = {}
    child_offset = mhii_offset + header_size
    mhii_end = mhii_offset + total_len
    for _ in range(child_count):
        _require_tag(data, child_offset, b"mhod")
        mhod_header_size = _u32(data, child_offset + 4)
        mhod_total = _u32(data, child_offset + 8)
        mhod_type = _u16(data, child_offset + 12)
        if mhod_type == ArtworkMhodType.THUMBNAIL_IMAGE:
            ref = _parse_mhni(data, child_offset + mhod_header_size)
            formats[ref.format_id] = ref
        child_offset += mhod_total
        if child_offset > mhii_end:
            raise ValueError(f"MHII en {mhii_offset}: hijo desbordó el chunk")

    return ParsedImageEntry(img_id, db_track_id, src_img_size, formats)


def read_artworkdb(data: bytes) -> List[ParsedImageEntry]:
    """Reconstruye las entradas MHII (img_id/song_id/formatos) de un ArtworkDB.

    Pensado para verificar en staging lo que este mismo escritor acaba de
    producir (Etapa 4c) — no lleva el blindaje defensivo de
    ``read_existing_artwork`` de iOpenPod contra ArtworkDB de terceros
    corruptos; ver docstring del módulo.
    """
    _require_tag(data, 0, b"mhfd")
    mhfd_header_size = _u32(data, 4)
    num_datasets = _u32(data, 20)

    entries: List[ParsedImageEntry] = []
    offset = mhfd_header_size
    for _ in range(num_datasets):
        _require_tag(data, offset, b"mhsd")
        mhsd_header_size = _u32(data, offset + 4)
        mhsd_total = _u32(data, offset + 8)
        ds_type = _u16(data, offset + 12)

        if ds_type == ArtworkDatasetType.IMAGE_LIST:
            mhli_offset = offset + mhsd_header_size
            _require_tag(data, mhli_offset, b"mhli")
            mhli_header_size = _u32(data, mhli_offset + 4)
            mhii_count = _u32(data, mhli_offset + 8)
            pos = mhli_offset + mhli_header_size
            for _ in range(mhii_count):
                entry = _parse_mhii(data, pos)
                entries.append(entry)
                pos += _u32(data, pos + 8)

        offset += mhsd_total

    return entries
