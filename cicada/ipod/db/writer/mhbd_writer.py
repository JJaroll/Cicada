"""MHBD Writer — Write complete iTunesDB database files.

This is the top-level writer that assembles all components into
a valid iTunesDB (or iTunesCDB for Nano 5G+) file.

Dataset write order (matches libgpod):
  mhbd (database header, 244 bytes)
    mhsd type 1 (tracks dataset)
      mhlt (track list)
        mhit (track) x N
          mhod (string) x M
    mhsd type 3 (playlist dataset with podcast-aware grouping)
      mhlp (playlist list) — often mirrors type 2, but remains distinct
    mhsd type 2 (playlists dataset)
      mhlp (playlist list)
        mhyp (master playlist) — REQUIRED, always first
          mhod types 52/53 (library indices)
          mhip (track ref) x N
        mhyp (user playlist) x M
    mhsd type 4 (albums dataset)
      mhla (album list)
        mhia (album item) x N
    mhsd type 8 (artist list)
      mhli (artist list)
        mhii (artist item) x N
          mhod type 300 (artist name)
    mhsd type 6 (empty stub — mhlt with 0 children)
    mhsd type 10 (empty stub — mhlt with 0 children)
    mhsd type 5 (smart playlists dataset)
      mhlp (smart playlist list)

MHBD header layout (MHBD_HEADER_SIZE = 244 bytes):
    +0x00: 'mhbd' magic (4B)
    +0x04: header_length (4B)
    +0x08: total_length (4B) — entire file size
    +0x0C: unk1 (4B) — always 1
    +0x10: version (4B) — 0x4F
    +0x14: children_count (4B) — 5
    +0x18: database_id (8B)
    +0x20: platform (2B) — 1=Mac, 2=Windows
    +0x22: unk_0x22 (2B) — ~611
    +0x24: db_id_2 (8B) — secondary ID (written in every MHIT)
    +0x2C: unk_0x2c (4B)
    +0x30: hashing_scheme (2B) — 0=none, 1=hash58
    +0x32: unk_0x32 (20B) — zeroed before hash58
    +0x46: language (2B)
    +0x48: lib_persistent_id (8B)
    +0x50: unk_0x50 (4B)
    +0x54: unk_0x54 (4B)
    +0x58: hash58 (20B)
    +0x6C: timezone_offset (4B signed)
    +0x70: unk_0x70 (2B)
    +0x72: hash72 (46B)
    +0xA0: audio_language (2B)
    +0xA2: subtitle_language (2B)

Cross-referenced against:
  - src/iopenpod/itunesdb_parser/mhbd_parser.py parse_db()
  - libgpod itdb_itunesdb.c: mk_mhbd() / parse_mhbd()
"""

import logging
import random
import struct
import time
import zlib
from dataclasses import replace as _dc_replace

from cicada.ipod.device.checksum import ChecksumType
from cicada.ipod.device.capabilities import DeviceCapabilities
from cicada.ipod.db.shared.album_identity import album_identity_from_track
from cicada.ipod.db.shared.device_time import active_device_time_context
from cicada.ipod.db.shared.field_base import (
    read_fields,
    write_fields,
    write_generic_header,
)
from cicada.ipod.db.shared.mhbd_defs import MHBD_HEADER_SIZE

from .mhit_writer import TrackInfo
from .mhla_writer import write_mhla
from .mhli_writer import write_mhli
from .mhlp_writer import write_mhlp_smart, write_mhlp_with_playlists
from .mhlt_writer import write_mhlt
from .mhsd_writer import (
    write_mhsd_empty_stub,
    write_mhsd_smart_type5,
    write_mhsd_type1,
    write_mhsd_type2,
    write_mhsd_type3,
    write_mhsd_type4,
    write_mhsd_type8,
)
from .mhyp_writer import PlaylistInfo, generate_playlist_id

logger = logging.getLogger(__name__)

DATABASE_VERSION_DEFAULT = 0x4F


def _maybe_decompress_cdb(itdb_data: bytes) -> bytes:
    """Decompress an iTunesCDB payload if the compressed indicator is set.

    Returns the full (header + decompressed children) bytes if the data
    is a compressed iTunesCDB, or the original bytes unchanged otherwise.
    """
    hdr_len = struct.unpack("<I", itdb_data[4:8])[0]
    if len(itdb_data) > hdr_len + 2 and struct.unpack("<H", itdb_data[0xA8:0xAA])[0] == 1 and itdb_data[hdr_len] == 0x78:
        try:
            decompressed = zlib.decompress(itdb_data[hdr_len:])
            return itdb_data[:hdr_len] + decompressed
        except zlib.error:
            pass
    return itdb_data


def _valid_itunesdb_platform(itdb_data: bytes | None) -> int | None:
    """Read a valid MHBD platform flag without trusting other header fields."""
    if not itdb_data or len(itdb_data) < 0x22 or itdb_data[:4] != b"mhbd":
        return None
    platform = struct.unpack_from("<H", itdb_data, 0x20)[0]
    return platform if platform in (1, 2) else None


def _validate_existing_itunesdb(itdb_data: bytes, path: str) -> None:
    """Reject an existing on-device database that is unsafe to rewrite from."""
    if len(itdb_data) < MHBD_HEADER_SIZE or itdb_data[:4] != b"mhbd":
        raise RuntimeError(f"The existing iPod database is truncated or malformed: {path}. iOpenPod stopped before replacing it.")
    header_len = struct.unpack_from("<I", itdb_data, 4)[0]
    total_len = struct.unpack_from("<I", itdb_data, 8)[0]
    if header_len < MHBD_HEADER_SIZE or header_len > total_len or total_len > len(itdb_data):
        raise RuntimeError(f"The existing iPod database has invalid size fields: {path}. iOpenPod stopped before replacing it.")
    compressed = struct.unpack_from("<H", itdb_data, 0xA8)[0] == 1
    if compressed:
        try:
            zlib.decompress(itdb_data[header_len:total_len])
        except zlib.error as exc:
            raise RuntimeError(f"The existing compressed iPod database is corrupt: {path}. iOpenPod stopped before replacing it.") from exc


def extract_db_info(itdb_path: str) -> dict:
    """
    Extract useful information from an existing iTunesDB.

    This can be used to get:
    - db_id: To preserve identity across rewrites
    - hashing_scheme: What hash type is used
    - hash58/hash72: The actual hash values

    All keys use canonical ``field_defs`` names (e.g. ``'db_id_2'`` not
    ``'db_id_2'``, ``'timezone_offset'`` not ``'timezone'``).

    Args:
        itdb_path: Path to iTunesDB file

    Returns:
        Dictionary with extracted information (field_defs key names)
    """
    with open(itdb_path, "rb") as f:
        data = f.read(MHBD_HEADER_SIZE)

    if data[:4] != b"mhbd":
        raise ValueError(f"Not an iTunesDB file: {itdb_path}")

    header_length = struct.unpack_from("<I", data, 4)[0]
    return read_fields(data, 0, "mhbd", header_length)


def extract_preserved_mhsd_blobs(itdb_data: bytes) -> list[bytes]:
    """Extract raw MHSD blobs for dataset types we don't generate.

    iTunes 9+ writes additional MHSD children for Genius features
    (types 6-10).  We now generate types 6, 8, and 10 ourselves
    (empty stubs for 6/10, artist list for 8), so we only preserve
    types we don't generate: 7 and 9 (Genius Chill).

    Args:
        itdb_data: Complete original iTunesDB file bytes.

    Returns:
        List of raw MHSD byte blobs for dataset types we don't generate,
        in the order they appeared in the original database.
    """
    if len(itdb_data) < 24 or itdb_data[:4] != b"mhbd":
        return []

    header_length = struct.unpack("<I", itdb_data[4:8])[0]

    itdb_data = _maybe_decompress_cdb(itdb_data)

    children_count = struct.unpack("<I", itdb_data[0x14:0x18])[0]

    GENERATED_TYPES = {1, 2, 3, 4, 5, 6, 8, 10}

    blobs: list[bytes] = []
    offset = header_length

    for _ in range(children_count):
        if offset + 16 > len(itdb_data):
            break
        magic = itdb_data[offset : offset + 4]
        if magic != b"mhsd":
            break
        mhsd_total = struct.unpack("<I", itdb_data[offset + 8 : offset + 12])[0]
        mhsd_type = struct.unpack("<I", itdb_data[offset + 12 : offset + 16])[0]

        if mhsd_type not in GENERATED_TYPES:
            blob = itdb_data[offset : offset + mhsd_total]
            blobs.append(bytes(blob))
            logger.debug("Preserved MHSD type %d blob (%d bytes)", mhsd_type, mhsd_total)

        offset += mhsd_total

    if blobs:
        logger.info("Preserved %d extra MHSD blob(s) from existing database.", len(blobs))
    return blobs


def generate_database_id() -> int:
    """Generate a random 64-bit database ID."""
    return random.getrandbits(64)


def write_mhbd(
    tracks: list[TrackInfo],
    db_id: int | None = None,
    language: str = "en",
    reference_info: dict | None = None,
    playlists_type2: list[PlaylistInfo] | None = None,
    playlists_type3: list[PlaylistInfo] | None = None,
    playlists_type5: list[PlaylistInfo] | None = None,
    preserved_mhsd_blobs: list[bytes] | None = None,
    capabilities: DeviceCapabilities | None = None,
    master_playlist_name: str = "iPod",
    master_playlist_id: int | None = None,
    podcast_master_playlist_name: str | None = None,
    podcast_master_playlist_id: int | None = None,
    *,
    platform: int | None = None,
) -> bytes:
    """
    Write a complete iTunesDB database.

    Args:
        tracks: List of TrackInfo objects to include
        db_id: Database ID (generated if not provided)
        language: 2-letter language code
        reference_info: Dict from extract_db_info() to copy device-specific fields
        playlists_type2: List of PlaylistInfo for user playlists (dataset 2).
                   Master playlist is auto-generated; does NOT belong in this list.
        playlists_type3: List of PlaylistInfo for podcast-list playlists
                         (dataset 3). If None, dataset 2 playlists are cloned
                         for libgpod-compatible new-database output. Passing
                         an empty list is meaningful: write dataset 3 with
                         only its generated master playlist.
        playlists_type5: List of PlaylistInfo for dataset 5 smart playlists
                         (iPod browsing categories like Music, Movies, etc.)
        preserved_mhsd_blobs: Raw MHSD byte blobs (types 6+) extracted from
                              an existing database via extract_preserved_mhsd_blobs().
                              Appended verbatim after the 5 standard datasets to
                              preserve Genius and other iTunes-generated data.
        capabilities: Device capabilities from ``ipod_device``.  When provided,
                      ``db_version`` and ``supports_podcast`` are respected.
        master_playlist_name: Display name for the dataset 2 master playlist.
        master_playlist_id: Existing dataset 2 master playlist ID, if any.
        podcast_master_playlist_name: Display name for the dataset 3 master
                                      playlist. Defaults to master_playlist_name.
        podcast_master_playlist_id: Existing dataset 3 master playlist ID, if any.
        platform: Explicit MHBD OS flag (1=Mac, 2=Windows). When omitted,
                  preserves a valid value from ``reference_info``.

    Returns:
        Complete iTunesDB file content as bytes
    """
    if db_id is None:
        if reference_info and "db_id" in reference_info:
            db_id = reference_info["db_id"]
        else:
            db_id = generate_database_id()

    if reference_info and "db_id_2" in reference_info:
        db_id_2 = reference_info["db_id_2"]
    else:
        db_id_2 = random.getrandbits(64)

    global_id_start_index = 1

    mhla_data, album_map, last_id = write_mhla(tracks, starting_index_for_album_id=global_id_start_index)
    mhsd_type4 = write_mhsd_type4(mhla_data)

    mhli_data, artist_map, last_id = write_mhli(tracks, starting_index_for_artist_id=last_id + 1)
    mhsd_type8 = write_mhsd_type8(mhli_data)

    composer_map: dict[str, int] = {}
    composer_id = last_id + 1
    for track in tracks:
        composer_name = track.composer or ""
        if not composer_name:
            continue
        key = composer_name.lower()
        if key not in composer_map:
            composer_map[key] = composer_id
            composer_id += 1
    last_id = composer_id - 1 if composer_map else last_id

    for track in tracks:
        if not track.album_id:
            identity = album_identity_from_track(track)
            album_name = identity.album or ""
            album_artist = identity.album_artist or identity.artist or ""
            key = (album_name, album_artist)
            track.album_id = album_map.get(key, 0)

        artist_name = track.artist or ""
        if artist_name:
            track.artist_id = artist_map.get(artist_name.lower(), 0)

        composer_name = track.composer or ""
        if composer_name:
            track.composer_id = composer_map.get(composer_name.lower(), 0)

    ref_version = reference_info.get("version", 0) if reference_info else 0
    cap_version = capabilities.db_version if capabilities else 0
    if cap_version:
        db_version = max(ref_version, cap_version)
    elif ref_version:
        db_version = ref_version
    else:
        db_version = DATABASE_VERSION_DEFAULT
    logger.debug("Using db_version=0x%X (ref=0x%X, cap=0x%X, default=0x%X)", db_version, ref_version, cap_version, DATABASE_VERSION_DEFAULT)


    mhlt_data, next_track_id = write_mhlt(tracks, db_id_2=db_id_2, capabilities=capabilities, db_version=db_version, start_track_id=last_id + 1)
    mhsd_type1 = write_mhsd_type1(mhlt_data)

    track_ids = list(range(last_id + 1, next_track_id))

    db_track_id_to_track_id: dict[int, int] = {}
    for i, track in enumerate(tracks):
        if track.db_track_id:
            db_track_id_to_track_id[track.db_track_id] = i + last_id + 1

    def _remap_playlist(pl: PlaylistInfo) -> PlaylistInfo:
        """Return a copy of pl with the db_track_ids translated to track IDs."""
        new_ids: list[int] = []
        new_meta: list | None = [] if pl.item_metadata is not None else None

        meta = pl.item_metadata
        for i, db_track_id in enumerate(pl.track_ids):
            track_id = db_track_id_to_track_id.get(db_track_id)
            if track_id is None:
                continue
            new_ids.append(track_id)
            if new_meta is not None and meta is not None and i < len(meta):
                new_meta.append(meta[i])

        if new_meta is not None and len(new_meta) != len(new_ids):
            new_meta = None

        return _dc_replace(pl, track_ids=new_ids, item_metadata=new_meta)

    remapped_playlists_type2 = [_remap_playlist(pl) for pl in (playlists_type2 or [])]
    if master_playlist_id is None:
        master_playlist_id = generate_playlist_id()
    mhsd_type2_data = write_mhlp_with_playlists(
        track_ids,
        playlists=remapped_playlists_type2,
        tracks=tracks,
        db_id_2=db_id_2,
        capabilities=capabilities,
        master_playlist_name=master_playlist_name,
        master_playlist_id=master_playlist_id,
    )
    mhsd_type2 = write_mhsd_type2(mhsd_type2_data)


    include_podcasts = True
    if capabilities is not None and not capabilities.supports_podcast:
        include_podcasts = False

    if include_podcasts:
        source_playlists_type3 = playlists_type2 if playlists_type3 is None else playlists_type3
        remapped_playlists_type3 = [_remap_playlist(pl) for pl in (source_playlists_type3 or [])]
        if podcast_master_playlist_id is None:
            podcast_master_playlist_id = generate_playlist_id()
        track_album_map: dict[int, str] = {}
        for i, track in enumerate(tracks):
            seq_id = i + last_id + 1
            track_album_map[seq_id] = track.album or ""

        from .mhlp_writer import write_mhlp_with_playlists_type3

        mhsd_type3_data = write_mhlp_with_playlists_type3(
            track_ids,
            playlists=remapped_playlists_type3,
            db_id_2=db_id_2,
            track_album_map=track_album_map,
            tracks=tracks,
            capabilities=capabilities,
            master_playlist_name=podcast_master_playlist_name or master_playlist_name,
            next_mhip_id_start=next_track_id,
            master_playlist_id=podcast_master_playlist_id,
        )
        mhsd_type3 = write_mhsd_type3(mhsd_type3_data)
    else:
        mhsd_type3 = b""

    remapped_playlists_type5 = [_remap_playlist(pl) for pl in (playlists_type5 or [])]
    mhsd_type5_data = write_mhlp_smart(remapped_playlists_type5, db_id_2=db_id_2)
    mhsd_type5 = write_mhsd_smart_type5(mhsd_type5_data)

    mhsd_type6 = write_mhsd_empty_stub(6)
    mhsd_type10 = write_mhsd_empty_stub(10)


    ref_types: set[int] | None = None
    ref_order: list[int] | None = None
    if reference_info and "mhsd_types" in reference_info:
        rt = reference_info["mhsd_types"]
        if rt and 1 in rt:
            ref_types = rt
            ref_order = reference_info.get("mhsd_order")
        logger.debug("Reference MHSD types: %s (order: %s)", sorted(ref_types) if ref_types else "none (fallback to all)", ref_order if ref_order else "default")

    legacy_excluded_types: set[int] = set()
    if capabilities is not None and capabilities.db_version <= 0x19:
        legacy_excluded_types = {6, 8, 10}

    required_ref_types: set[int] = set()
    if ref_types is not None:
        required_ref_types.add(1)
        needs_regular_playlist_dataset = False
        if 2 in ref_types:
            required_ref_types.add(2)
            needs_regular_playlist_dataset = True
        if include_podcasts and 3 in ref_types:
            required_ref_types.add(3)
            needs_regular_playlist_dataset = True
        if needs_regular_playlist_dataset:
            required_ref_types.add(2)
        if not required_ref_types.intersection({2, 3}):
            required_ref_types.add(2)


    def _include(dtype: int, required: bool = False) -> bool:
        if dtype in legacy_excluded_types:
            return False
        if required:
            return True
        if ref_types is None:
            return True
        return dtype in ref_types

    type_to_data: dict[int, bytes] = {
        1: mhsd_type1,
        2: mhsd_type2,
        3: mhsd_type3 if (include_podcasts and mhsd_type3) else b"",
        4: mhsd_type4,
        5: mhsd_type5,
        6: mhsd_type6,
        8: mhsd_type8,
        10: mhsd_type10,
    }

    dataset_entries: list[tuple[int, bytes]] = []
    if ref_order:
        inserted_required_type2 = False
        for dtype in ref_order:
            if dtype not in type_to_data:
                continue
            if dtype == 3 and not include_podcasts:
                continue
            if _include(dtype, required=(dtype in required_ref_types)):
                data = type_to_data[dtype]
                if data:
                    dataset_entries.append((dtype, data))
                    if dtype == 3 and 2 in required_ref_types and ref_types is not None and 2 not in ref_types and not inserted_required_type2:
                        dataset_entries.append((2, type_to_data[2]))
                        inserted_required_type2 = True
        for dtype in (1, 3, 2):
            if dtype not in required_ref_types:
                continue
            if not any(t == dtype for t, _ in dataset_entries):
                dataset_entries.append((dtype, type_to_data[dtype]))
    else:
        dataset_entries.append((1, mhsd_type1))
        if include_podcasts and _include(3):
            dataset_entries.append((3, mhsd_type3))
        if _include(2):
            dataset_entries.append((2, mhsd_type2))
        dataset_entries.append((4, mhsd_type4))
        if _include(8):
            dataset_entries.append((8, mhsd_type8))
        if _include(6):
            dataset_entries.append((6, mhsd_type6))
        if _include(10):
            dataset_entries.append((10, mhsd_type10))
        if _include(5):
            dataset_entries.append((5, mhsd_type5))

    all_datasets = b"".join(data for _, data in dataset_entries)
    child_count = len(dataset_entries)
    logger.debug("Writing %d MHSD datasets: %s", child_count, [t for t, _ in dataset_entries])

    extra_blobs = preserved_mhsd_blobs or []
    for blob in extra_blobs:
        all_datasets += blob
    child_count += len(extra_blobs)

    total_length = MHBD_HEADER_SIZE + len(all_datasets)


    compressed = 2 if (capabilities and capabilities.supports_compressed_db) else 1


    unk0x32 = b"\x00" * 20
    if reference_info and "unk0x32" in reference_info:
        raw = reference_info["unk0x32"]
        if isinstance(raw, (bytes, bytearray)) and len(raw) == 20:
            unk0x32 = bytes(raw)

    if reference_info and "language" in reference_info:
        lang_val = reference_info["language"]
        if isinstance(lang_val, str):
            lang_val = lang_val.encode("utf-8")[:2].ljust(2, b"\x00")
    else:
        lang_val = language.encode("utf-8")[:2].ljust(2, b"\x00")

    if reference_info and reference_info.get("db_persistent_id"):
        lib_pid = reference_info["db_persistent_id"]
    else:
        lib_pid = db_id

    time_context = active_device_time_context()
    if time_context is not None:
        tz_offset = time_context.offset_at_unix(int(time.time()))
    elif reference_info and "timezone_offset" in reference_info:
        tz_offset = reference_info["timezone_offset"]
    else:
        tz_offset = -time.altzone if time.daylight else -time.timezone

    if reference_info:
        hash_type_ind = reference_info.get("hash_type_indicator", 0)
    elif capabilities:
        _ck_to_ind = {ChecksumType.HASHAB: 4, ChecksumType.HASH72: 2}
        hash_type_ind = _ck_to_ind.get(capabilities.checksum, 0)
    else:
        hash_type_ind = 0


    platform_flag = platform
    if platform_flag not in (1, 2):
        platform_flag = reference_info.get("platform", 2) if reference_info else 2
    if platform_flag not in (1, 2):
        platform_flag = 2

    header = bytearray(MHBD_HEADER_SIZE)
    write_generic_header(header, 0, b"mhbd", MHBD_HEADER_SIZE, total_length)

    values: dict = {
        "compressed": compressed,
        "version": db_version,
        "child_count": child_count,
        "db_id": db_id,
        "platform": platform_flag,
        "unk0x22": reference_info.get("unk0x22", 611) if reference_info else 611,
        "db_id_2": db_id_2,
        "unk0x2c": 0,
        "hashing_scheme": 0,
        "unk0x32": unk0x32,
        "language": lang_val,
        "db_persistent_id": lib_pid,
        "unk0x50": reference_info.get("unk0x50", 1) if reference_info else 1,
        "unk0x54": reference_info.get("unk0x54", 15) if reference_info else 15,
        "timezone_offset": tz_offset,
        "hash_type_indicator": hash_type_ind,
    }

    if reference_info:
        for key in ("audio_language", "subtitle_language", "unk0xa4", "unk0xa6", "cdb_flag"):
            if key in reference_info:
                values[key] = reference_info[key]

    write_fields(header, 0, "mhbd", values, MHBD_HEADER_SIZE)

    return bytes(header) + all_datasets
