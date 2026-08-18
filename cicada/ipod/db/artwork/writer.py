"""Orquestador del escritor de ArtworkDB (Fase 4, Etapa 4c).

Produce bytes en memoria (ArtworkDB + un .ithmb por formato) — igual que
db/writer/build.py, aquí no se toca disco; escribirlos a
iPod_Control/Artwork/ es responsabilidad del coordinador (Etapa 4d), que
ya pasa por assert_within_ipod_control().

Reescritura completa siempre: cada llamada regenera el ArtworkDB entero a
partir de los tracks dados, sin dedup por hash ni preservación de entradas
existentes (decisión tomada en la Fase 4, con el coste medido contra una
biblioteca real: ~12s para reescribir todo). Cada track recibe su propio
img_id aunque comparta imagen con otro (p. ej. mismo álbum) — no hay tabla
de reuso que mantener ni invalidar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from cicada.ipod.db.artwork.chunks import build_artworkdb, ithmb_filename, write_mhii
from cicada.ipod.db.artwork.rgb565 import convert_art_for_format
from cicada.ipod.db.artwork.types import EncodedFormatPayload
from cicada.ipod.device.artwork_presets import ArtworkFormat, NANO_7G_COVER_ART_FORMATS

DEFAULT_START_IMG_ID = 100


@dataclass(frozen=True)
class ArtworkSourceTrack:
    """Una pista con su carátula ya extraída (ver cicada.shared.artwork)."""

    db_track_id: int
    art_bytes: bytes


@dataclass(frozen=True)
class ArtworkTrackResult:
    """Lo que el llamador necesita para poblar TrackInfo (Etapa 4d)."""

    img_id: int
    src_img_size: int


@dataclass(frozen=True)
class ArtworkBuildResult:
    artworkdb: bytes
    ithmb_files: Dict[str, bytes] = field(default_factory=dict)
    track_artwork: Dict[int, ArtworkTrackResult] = field(default_factory=dict)
    skipped_track_ids: Tuple[int, ...] = ()


def build_artwork_assets(
    tracks: List[ArtworkSourceTrack],
    *,
    formats: Tuple[ArtworkFormat, ...] = NANO_7G_COVER_ART_FORMATS,
    start_img_id: int = DEFAULT_START_IMG_ID,
) -> ArtworkBuildResult:
    """Construye ArtworkDB + .ithmb para los tracks dados.

    Tracks cuya imagen no se puede decodificar se omiten (sin img_id
    asignado, sin entrada MHII) en vez de fallar toda la construcción —
    el llamador los deja en has_artwork=2 (comportamiento ya existente,
    ver mhit_writer.py) igual que un track sin carátula.
    """
    ithmb_buffers: Dict[int, bytearray] = {fmt.format_id: bytearray() for fmt in formats}
    filenames: Dict[int, str] = {fmt.format_id: ithmb_filename(fmt.format_id) for fmt in formats}

    mhii_blobs: List[bytes] = []
    track_artwork: Dict[int, ArtworkTrackResult] = {}
    skipped: List[int] = []

    next_img_id = start_img_id
    for track in tracks:
        payloads: Dict[int, EncodedFormatPayload] = {}
        decodable = True
        for fmt in formats:
            payload = convert_art_for_format(track.art_bytes, fmt)
            if payload is None:
                decodable = False
                break
            payloads[fmt.format_id] = payload

        if not decodable:
            skipped.append(track.db_track_id)
            continue

        img_id = next_img_id
        next_img_id += 1

        offsets: Dict[int, int] = {}
        for fmt_id, payload in payloads.items():
            buf = ithmb_buffers[fmt_id]
            offsets[fmt_id] = len(buf)
            buf.extend(payload.data)

        mhii_blobs.append(
            write_mhii(
                img_id=img_id,
                db_track_id=track.db_track_id,
                src_img_size=len(track.art_bytes),
                formats=payloads,
                offsets=offsets,
                filenames=filenames,
            )
        )
        track_artwork[track.db_track_id] = ArtworkTrackResult(img_id=img_id, src_img_size=len(track.art_bytes))

    format_ids = [fmt.format_id for fmt in formats]
    image_sizes = {fmt.format_id: fmt.row_bytes * fmt.height for fmt in formats}

    artworkdb = build_artworkdb(mhii_blobs, format_ids, image_sizes, next_img_id)
    ithmb_files = {filenames[fid]: bytes(buf) for fid, buf in ithmb_buffers.items()}

    return ArtworkBuildResult(
        artworkdb=artworkdb,
        ithmb_files=ithmb_files,
        track_artwork=track_artwork,
        skipped_track_ids=tuple(skipped),
    )
