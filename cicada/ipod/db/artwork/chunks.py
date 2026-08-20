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

**MHBA/MHIA (Fase 6, Etapa 6f)**: el "Photo Database" del dispositivo usa
el MISMO contenedor mhfd→mhsd→{mhli,mhla,mhlf} que ArtworkDB — confirmado
byte a byte contra `sync/photos.py` de iOpenPod (headers idénticos:
MHFD/MHSD/MHLI/MHLA/MHLF/MHII/MHOD/MHNI/MHIF). Lo único que faltaba a nivel
de chunk era `mhba` (entrada de álbum) y `mhia` (membresía), que
`write_mhla()` nunca necesitó porque ArtworkDB (cover art) siempre escribe
0 álbumes. El `MHII` de Fotos usa offsets DISTINTOS a los de cover art
pese a compartir tamaño de header (152 bytes): cover art guarda
`song_id`/`db_track_id` en el offset 20; Fotos usa ese rango para otra
cosa y guarda `created_at`/`digitized_at`/`original_size` en 40/44/48. Por
eso `write_mhii_photo`/`_parse_mhii_photo` son variantes separadas de
`write_mhii`/`_parse_mhii`, no una generalización de las mismas — mismo
tamaño de header, semántica de campos incompatible.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import PurePosixPath
from typing import Dict, List, Optional

from cicada.ipod.db.artwork.types import EncodedFormatPayload, PhotoAlbumInput

MHFD_HEADER_SIZE = 132
MHSD_HEADER_SIZE = 96
MHLI_HEADER_SIZE = 92
MHLA_HEADER_SIZE = 92
MHLF_HEADER_SIZE = 92
MHII_HEADER_SIZE = 152
MHOD_HEADER_SIZE = 24
MHNI_HEADER_SIZE = 76
MHIF_HEADER_SIZE = 124
MHBA_HEADER_SIZE = 148
MHIA_HEADER_SIZE = 40

#: format_id centinela para el MHNI de "Full Resolution" dentro de un MHII
#: de Fotos — no es un format_id real de ARTWORK_FORMATS_BY_ID (todos son
#: >= 1005), lo fija iOpenPod así (`_write_mhii`, `_write_mhni(1, 0, ...)`).
PHOTO_FULL_RESOLUTION_FORMAT_ID = 1


class ArtworkDatasetType(IntEnum):
    IMAGE_LIST = 1
    PHOTO_ALBUM_LIST = 2
    FILE_LIST = 3


class ArtworkMhodType(IntEnum):
    ALBUM_NAME = 1
    THUMBNAIL_IMAGE = 2
    FILE_NAME = 3
    FULL_RESOLUTION = 5
    UNKNOWN_MHAF = 6


#: Payload crudo (96 bytes, tag "mhaf" + 2 u32 + relleno cero) del 4º hijo
#: que Música/iTunes agrega a TODO MHII de Fotos (MHOD tipo 6), ausente en
#: iOpenPod y en Cicada hasta ahora. Confirmado idéntico byte a byte en las
#: 61 entradas de un Photo Database real escrito por Música (Etapa 6j,
#: 2026-08-20) — nunca varía con la foto, por eso se copia tal cual en vez
#: de reconstruirse: no se entiende su semántica interna, pero su
#: contenido no depende de nada que Cicada pueda calcular. Ver
#: docs/VENDORED.md, Paquete 9, para el detalle de la auditoría.
MHAF_STATIC_BLOB = bytes.fromhex(
    "6d686166600000003c00000000000000"
    "00000000000000000000000000000000"
    "00000000000000000000000000000000"
    "00000000000000000000000000000000"
    "00000000000000000000000000000000"
    "00000000000000000000000000000000"
)


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


def _write_mhod_string(mhod_type: int, value: str) -> bytes:
    """MHOD genérico de string UTF-16LE, sin el prefijo ':' automático de
    :func:`_write_mhod_filename` (Fotos, Etapa 6f: nombres de álbum y rutas
    ya vienen con la convención HFS aplicada por el llamador, ver
    :func:`photo_rel_path_to_db_string`). Separado de
    ``_write_mhod_filename`` a propósito — cero riesgo de tocar el camino
    de cover art ya verificado desde 4c."""
    encoded = value.encode("utf-16-le")
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
    struct.pack_into("<H", header, 12, mhod_type)
    return bytes(header) + body


def photo_rel_path_to_db_string(rel_path: str) -> str:
    """``"Thumbs/F1005_1.ithmb"`` -> ``":Thumbs:F1005_1.ithmb"`` (convención
    HFS de iTunes para rutas dentro de ``Photos/``). Adaptado de
    ``_photo_rel_path_to_db_string`` en ``sync/photos.py`` de iOpenPod."""
    return ":" + ":".join(PurePosixPath(rel_path).parts)


def photo_db_string_to_rel_path(value: str) -> str:
    """Inversa de :func:`photo_rel_path_to_db_string`."""
    cleaned = value[1:] if value.startswith(":") else value
    return cleaned.replace(":", "/")


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


def write_mhni_photo(format_id: int, ithmb_offset: int, payload: EncodedFormatPayload, storage_path: str) -> bytes:
    """Variante de :func:`write_mhni` para Fotos (Etapa 6f): mismo header de
    76 bytes, pero el hijo MHOD tipo FILE_NAME lleva una ruta relativa
    completa con convención HFS (``":Thumbs:F1005_1.ithmb"``,
    ``":Full Resolution:iOpenPod:foto_00123.jpg"``), no un nombre de
    archivo plano — a diferencia de cover art, donde el .ithmb vive junto
    al ArtworkDB y un nombre plano alcanza."""
    mhod_path = _write_mhod_string(ArtworkMhodType.FILE_NAME, photo_rel_path_to_db_string(storage_path))
    total_len = MHNI_HEADER_SIZE + len(mhod_path)

    if payload.vpad > 0x7FFF or payload.hpad > 0x7FFF:
        raise ValueError(f"Padding demasiado grande para format {format_id}: {payload}")

    header = bytearray(MHNI_HEADER_SIZE)
    header[0:4] = b"mhni"
    struct.pack_into("<I", header, 4, MHNI_HEADER_SIZE)
    struct.pack_into("<I", header, 8, total_len)
    struct.pack_into("<I", header, 12, 1)  # child_count: solo el mhod de ruta
    struct.pack_into("<I", header, 16, format_id)
    struct.pack_into("<I", header, 20, ithmb_offset)
    struct.pack_into("<I", header, 24, payload.size)
    struct.pack_into("<h", header, 28, payload.vpad)
    struct.pack_into("<h", header, 30, payload.hpad)
    struct.pack_into("<H", header, 32, payload.height)
    struct.pack_into("<H", header, 34, payload.width)
    struct.pack_into("<I", header, 40, payload.size)
    return bytes(header) + mhod_path


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


def write_mhii_photo(
    image_id: int,
    *,
    created_at: int,
    digitized_at: int,
    original_size: int,
    full_res_payload: EncodedFormatPayload,
    full_res_storage_path: str,
    thumb_formats: Dict[int, EncodedFormatPayload],
    thumb_offsets: Dict[int, int],
    thumb_storage_paths: Dict[int, str],
) -> bytes:
    """Variante de :func:`write_mhii` para Fotos (Etapa 6f) — MISMO tamaño de
    header (152 bytes) que cover art, semántica de campos DISTINTA: cover
    art guarda ``song_id``/``db_track_id`` en offset 20 (u64); Fotos deja
    ese rango sin usar y guarda ``created_at``/``digitized_at``/
    ``original_size`` en 40/44/48 (u32 cada uno). No reusar
    :func:`write_mhii` para Fotos — mismo tamaño de header con semántica
    incompatible es exactamente el tipo de error silencioso que un test
    superficial ("parsea sin excepción") no atraparía.

    El primer hijo siempre es el MHOD tipo FULL_RESOLUTION (5) envolviendo
    el MHNI de la imagen completa (``format_id`` centinela
    :data:`PHOTO_FULL_RESOLUTION_FORMAT_ID`); siguen los MHOD tipo
    THUMBNAIL_IMAGE (2), uno por formato de miniatura, en orden de
    ``format_id`` ascendente (mismo criterio de orden que ``write_mhii``);
    el último es un MHOD tipo UNKNOWN_MHAF (6) con :data:`MHAF_STATIC_BLOB`
    — presente en las 61 entradas de un Photo Database real de referencia
    pero ausente en toda escritura previa de Cicada/iOpenPod (Etapa 6j).

    Offset 20 del header (u32, sin uso documentado hasta ahora): se
    escribe ``image_id + 2``, patrón empírico confirmado sin excepción en
    las 61 entradas de esa misma referencia real (rango de image_id
    100-160). No se conoce su semántica — podría ser un id persistente
    distinto del índice, un contador de sesión, u otra cosa — solo que la
    fórmula reproduce exactamente lo observado en una única sesión de
    sync real; ver docs/VENDORED.md, Paquete 9, para el detalle completo
    y la advertencia de que una sola sesión no basta para probar que es
    una ley general (mismo tipo de cautela que offset 48 de MHFD).
    """
    children = [
        _write_mhod_container(
            ArtworkMhodType.FULL_RESOLUTION,
            write_mhni_photo(PHOTO_FULL_RESOLUTION_FORMAT_ID, 0, full_res_payload, full_res_storage_path),
        )
    ]
    children.extend(
        _write_mhod_container(
            ArtworkMhodType.THUMBNAIL_IMAGE,
            write_mhni_photo(fmt_id, thumb_offsets[fmt_id], thumb_formats[fmt_id], thumb_storage_paths[fmt_id]),
        )
        for fmt_id in sorted(thumb_formats.keys())
    )
    children.append(_write_mhod_container(ArtworkMhodType.UNKNOWN_MHAF, MHAF_STATIC_BLOB))
    children_data = b"".join(children)
    total_len = MHII_HEADER_SIZE + len(children_data)

    header = bytearray(MHII_HEADER_SIZE)
    header[0:4] = b"mhii"
    struct.pack_into("<I", header, 4, MHII_HEADER_SIZE)
    struct.pack_into("<I", header, 8, total_len)
    struct.pack_into("<I", header, 12, len(children))
    struct.pack_into("<I", header, 16, image_id)
    struct.pack_into("<I", header, 20, image_id + 2)
    struct.pack_into("<I", header, 40, created_at)
    struct.pack_into("<I", header, 44, digitized_at)
    struct.pack_into("<I", header, 48, original_size)
    return bytes(header) + children_data


def write_mhli(mhii_blobs: List[bytes]) -> bytes:
    header = bytearray(MHLI_HEADER_SIZE)
    header[0:4] = b"mhli"
    struct.pack_into("<I", header, 4, MHLI_HEADER_SIZE)
    struct.pack_into("<I", header, 8, len(mhii_blobs))
    return bytes(header) + b"".join(mhii_blobs)


def write_mhia(image_id: int) -> bytes:
    """MHIA (40 bytes): membresía de una foto en un álbum, solo ``image_id``."""
    header = bytearray(MHIA_HEADER_SIZE)
    header[0:4] = b"mhia"
    struct.pack_into("<I", header, 4, MHIA_HEADER_SIZE)
    struct.pack_into("<I", header, 8, MHIA_HEADER_SIZE)
    struct.pack_into("<I", header, 16, image_id)
    return bytes(header)


def write_mhba(album: PhotoAlbumInput) -> bytes:
    """MHBA (148 bytes): un álbum de fotos — nombre (MHOD tipo ALBUM_NAME) +
    un MHIA por miembro. Layout confirmado byte a byte contra
    ``_write_mhba``/``PhotoAlbum`` en ``sync/photos.py`` de iOpenPod."""
    children = [_write_mhod_string(ArtworkMhodType.ALBUM_NAME, album.name)]
    children.extend(write_mhia(image_id) for image_id in album.members)
    children_data = b"".join(children)
    total_len = MHBA_HEADER_SIZE + len(children_data)

    header = bytearray(MHBA_HEADER_SIZE)
    header[0:4] = b"mhba"
    struct.pack_into("<I", header, 4, MHBA_HEADER_SIZE)
    struct.pack_into("<I", header, 8, total_len)
    struct.pack_into("<I", header, 12, 1)
    struct.pack_into("<I", header, 16, len(album.members))
    struct.pack_into("<I", header, 20, album.album_id)
    struct.pack_into("<H", header, 28, 0)
    header[30] = album.album_type & 0xFF
    header[31] = album.playmusic & 0xFF
    header[32] = album.repeat & 0xFF
    header[33] = album.random & 0xFF
    header[34] = album.show_titles & 0xFF
    header[35] = album.transition_direction & 0xFF
    struct.pack_into("<I", header, 36, album.slide_duration)
    struct.pack_into("<I", header, 40, album.transition_duration)
    struct.pack_into("<Q", header, 52, album.song_id)
    struct.pack_into("<I", header, 60, album.prev_album_id)
    return bytes(header) + children_data


def write_mhla(mhba_blobs: Optional[List[bytes]] = None) -> bytes:
    """Cover art (Etapa 4c) llama esto sin argumentos — 0 álbumes, nunca los
    necesitó. Fotos (Etapa 6f) pasa una lista real de MHBA."""
    blobs = mhba_blobs or []
    children_data = b"".join(blobs)
    header = bytearray(MHLA_HEADER_SIZE)
    header[0:4] = b"mhla"
    struct.pack_into("<I", header, 4, MHLA_HEADER_SIZE)
    struct.pack_into("<I", header, 8, len(blobs))
    return bytes(header) + children_data


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


#: Offset 48 (u32) del header MHFD: DELIBERADAMENTE sin escribir por ahora.
#: Un intento anterior lo fijó a 2, copiado sin más de que ambos
#: escritores originales de iOpenPod lo hacen así de forma incondicional.
#: Comparado luego contra un Photo Database REAL escrito por Música/iTunes
#: (Etapa 6h, 2026-08-20): el valor real ahí es 1, no 2 — y hay más bytes
#: no-cero alrededor (offset 52 = 2, más 24 bytes opacos en 32-48/60-68)
#: sin ningún patrón simple. Todo apunta a un contador de
#: generación/sesión o checksum, no una constante fija — escribir "1" en
#: vez de "2" sería el mismo error de raíz (copiar un valor de una fuente
#: que tampoco lo entendía). Se deja en 0 (el estado de antes de ese
#: intento) hasta entender qué es realmente. Ver docs/VENDORED.md,
#: Paquete 9, para el detalle completo de la auditoría.


def write_mhfd(datasets: List[bytes], next_img_id: int, *, unknown2: int = 2) -> bytes:
    """``unknown2``: 2 para ArtworkDB (cover art, valor histórico de 4c);
    Fotos (Etapa 6f) usa 6 — visto en `_DEFAULT_MHFD_UNKNOWN2` de
    ``sync/photos.py`` de iOpenPod, empírico contra bases reales de iTunes
    (Nano 2/6/7). Default preserva el comportamiento de cover art."""
    all_data = b"".join(datasets)
    total_len = MHFD_HEADER_SIZE + len(all_data)
    header = bytearray(MHFD_HEADER_SIZE)
    header[0:4] = b"mhfd"
    struct.pack_into("<I", header, 4, MHFD_HEADER_SIZE)
    struct.pack_into("<I", header, 8, total_len)
    struct.pack_into("<I", header, 16, unknown2)
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


def build_photo_db(
    mhii_blobs: List[bytes],
    mhba_blobs: List[bytes],
    format_ids: List[int],
    image_sizes: Dict[int, int],
    next_img_id: int,
) -> bytes:
    """Serializa el "Photo Database" completo — MISMO contenedor que
    :func:`build_artworkdb` (Etapa 6f), con álbumes reales en el dataset
    tipo PHOTO_ALBUM_LIST (que ArtworkDB siempre deja vacío) y
    ``unknown2=6`` en vez de 2. Los ``mhii_blobs`` deben venir de
    :func:`write_mhii_photo`, no de :func:`write_mhii` — mismo tamaño de
    header, semántica de campos distinta (ver docstring del módulo)."""
    ds1 = write_mhsd(ArtworkDatasetType.IMAGE_LIST, write_mhli(mhii_blobs))
    ds2 = write_mhsd(ArtworkDatasetType.PHOTO_ALBUM_LIST, write_mhla(mhba_blobs))
    ds3 = write_mhsd(ArtworkDatasetType.FILE_LIST, write_mhlf(format_ids, image_sizes))
    return write_mhfd([ds1, ds2, ds3], next_img_id, unknown2=6)


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


# ── Lectura de Fotos (Etapa 6f) ────────────────────────────────────────────


@dataclass(frozen=True)
class ParsedPhotoFormatRef:
    format_id: int
    ithmb_offset: int
    size: int
    width: int
    height: int
    hpad: int
    vpad: int
    storage_path: Optional[str]  # ya convertido a "/" (photo_db_string_to_rel_path)


@dataclass(frozen=True)
class ParsedPhotoImageEntry:
    image_id: int
    created_at: int
    digitized_at: int
    original_size: int
    full_res: Optional[ParsedPhotoFormatRef]
    thumbs: Dict[int, ParsedPhotoFormatRef] = field(default_factory=dict)
    persistent_id: int = 0  #: offset 20 del header MHII — ver docstring de write_mhii_photo
    has_mhaf_marker: bool = False  #: True si el MHII trae el 4º hijo MHOD tipo UNKNOWN_MHAF


@dataclass(frozen=True)
class ParsedPhotoAlbum:
    album_id: int
    name: str
    members: List[int]
    album_type: int
    playmusic: int
    repeat: int
    random: int
    show_titles: int
    transition_direction: int
    slide_duration: int
    transition_duration: int
    song_id: int
    prev_album_id: int


def _decode_mhod_path(data: bytes, mhod_offset: int) -> Optional[str]:
    raw = _decode_mhod_filename(data, mhod_offset)
    return photo_db_string_to_rel_path(raw) if raw is not None else None


def _parse_mhni_photo(data: bytes, mhni_offset: int) -> ParsedPhotoFormatRef:
    _require_tag(data, mhni_offset, b"mhni")
    header_size = _u32(data, mhni_offset + 4)
    format_id = _u32(data, mhni_offset + 16)
    ithmb_offset = _u32(data, mhni_offset + 20)
    size = _u32(data, mhni_offset + 24)
    vpad = _i16(data, mhni_offset + 28)
    hpad = _i16(data, mhni_offset + 30)
    height = _u16(data, mhni_offset + 32)
    width = _u16(data, mhni_offset + 34)

    storage_path = None
    child_offset = mhni_offset + header_size
    child_end = mhni_offset + _u32(data, mhni_offset + 8)
    while child_offset + MHOD_HEADER_SIZE <= child_end:
        _require_tag(data, child_offset, b"mhod")
        mhod_total = _u32(data, child_offset + 8)
        mhod_type = _u16(data, child_offset + 12)
        if mhod_type == ArtworkMhodType.FILE_NAME:
            storage_path = _decode_mhod_path(data, child_offset)
        child_offset += mhod_total

    return ParsedPhotoFormatRef(format_id, ithmb_offset, size, width, height, hpad, vpad, storage_path)


def _parse_mhii_photo(data: bytes, mhii_offset: int) -> ParsedPhotoImageEntry:
    _require_tag(data, mhii_offset, b"mhii")
    header_size = _u32(data, mhii_offset + 4)
    total_len = _u32(data, mhii_offset + 8)
    child_count = _u32(data, mhii_offset + 12)
    image_id = _u32(data, mhii_offset + 16)
    persistent_id = _u32(data, mhii_offset + 20)
    created_at = _u32(data, mhii_offset + 40)
    digitized_at = _u32(data, mhii_offset + 44)
    original_size = _u32(data, mhii_offset + 48)

    full_res: Optional[ParsedPhotoFormatRef] = None
    thumbs: Dict[int, ParsedPhotoFormatRef] = {}
    has_mhaf_marker = False
    child_offset = mhii_offset + header_size
    mhii_end = mhii_offset + total_len
    for _ in range(child_count):
        _require_tag(data, child_offset, b"mhod")
        mhod_header_size = _u32(data, child_offset + 4)
        mhod_total = _u32(data, child_offset + 8)
        mhod_type = _u16(data, child_offset + 12)
        if mhod_type == ArtworkMhodType.FULL_RESOLUTION:
            full_res = _parse_mhni_photo(data, child_offset + mhod_header_size)
        elif mhod_type == ArtworkMhodType.THUMBNAIL_IMAGE:
            ref = _parse_mhni_photo(data, child_offset + mhod_header_size)
            thumbs[ref.format_id] = ref
        elif mhod_type == ArtworkMhodType.UNKNOWN_MHAF:
            has_mhaf_marker = True
        child_offset += mhod_total
        if child_offset > mhii_end:
            raise ValueError(f"MHII (foto) en {mhii_offset}: hijo desbordó el chunk")

    return ParsedPhotoImageEntry(
        image_id, created_at, digitized_at, original_size, full_res, thumbs,
        persistent_id=persistent_id, has_mhaf_marker=has_mhaf_marker,
    )


def _parse_mhia(data: bytes, mhia_offset: int) -> int:
    _require_tag(data, mhia_offset, b"mhia")
    return _u32(data, mhia_offset + 16)


def _parse_mhba(data: bytes, mhba_offset: int) -> ParsedPhotoAlbum:
    _require_tag(data, mhba_offset, b"mhba")
    header_size = _u32(data, mhba_offset + 4)
    total_len = _u32(data, mhba_offset + 8)
    album_id = _u32(data, mhba_offset + 20)

    name = f"Album {album_id}"
    members: List[int] = []
    child_offset = mhba_offset + header_size
    mhba_end = mhba_offset + total_len
    while child_offset + 12 <= mhba_end:
        child_type = data[child_offset:child_offset + 4]
        child_total = _u32(data, child_offset + 8)
        if child_total <= 0:
            break
        if child_type == b"mhod":
            mhod_type = _u16(data, child_offset + 12)
            if mhod_type == ArtworkMhodType.ALBUM_NAME:
                decoded = _decode_mhod_filename(data, child_offset)
                if decoded is not None:
                    name = decoded
        elif child_type == b"mhia":
            members.append(_parse_mhia(data, child_offset))
        child_offset += child_total

    return ParsedPhotoAlbum(
        album_id=album_id,
        name=name,
        members=members,
        album_type=data[mhba_offset + 30],
        playmusic=data[mhba_offset + 31],
        repeat=data[mhba_offset + 32],
        random=data[mhba_offset + 33],
        show_titles=data[mhba_offset + 34],
        transition_direction=data[mhba_offset + 35],
        slide_duration=_u32(data, mhba_offset + 36),
        transition_duration=_u32(data, mhba_offset + 40),
        song_id=_u64(data, mhba_offset + 52),
        prev_album_id=_u32(data, mhba_offset + 60),
    )


def read_photo_db(data: bytes) -> tuple[List[ParsedPhotoImageEntry], List[ParsedPhotoAlbum]]:
    """Reconstruye imágenes (dataset IMAGE_LIST, semántica de Fotos) y
    álbumes (dataset PHOTO_ALBUM_LIST) de un "Photo Database" (Etapa 6f).

    Separado de :func:`read_artworkdb` a propósito — mismo contenedor
    mhfd/mhsd, pero el MHII de Fotos no es el MHII de cover art (ver
    docstring del módulo), así que reusar el parser de cover art leería
    campos equivocados en silencio.
    """
    _require_tag(data, 0, b"mhfd")
    mhfd_header_size = _u32(data, 4)
    num_datasets = _u32(data, 20)

    images: List[ParsedPhotoImageEntry] = []
    albums: List[ParsedPhotoAlbum] = []
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
                entry = _parse_mhii_photo(data, pos)
                images.append(entry)
                pos += _u32(data, pos + 8)
        elif ds_type == ArtworkDatasetType.PHOTO_ALBUM_LIST:
            mhla_offset = offset + mhsd_header_size
            _require_tag(data, mhla_offset, b"mhla")
            mhla_header_size = _u32(data, mhla_offset + 4)
            mhba_count = _u32(data, mhla_offset + 8)
            pos = mhla_offset + mhla_header_size
            for _ in range(mhba_count):
                album = _parse_mhba(data, pos)
                albums.append(album)
                pos += _u32(data, pos + 8)

        offset += mhsd_total

    return images, albums
