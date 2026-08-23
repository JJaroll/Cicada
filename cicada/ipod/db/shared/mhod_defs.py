"""MHOD (Data Object) field definitions and helpers.

Contains the :class:`FieldDef` list for the 24-byte common MHOD header,
plus type classification sets, string sub-header accessors, and
SPL / SLst / MHOD-52 / MHOD-53 / MHOD-100 / MHOD-102 parsing helpers.

The body-level layouts vary widely by MHOD type and do NOT fit the
simple ``FieldDef`` pattern, so they remain as hand-written helpers here.
"""

import struct

from .field_base import FieldDef, _u32

_S = "mhod"

MHOD_HEADER_SIZE: int = 24

MHOD_STRING_SUBHEADER_OFFSET = 0x18
MHOD_STRING_SUBHEADER_SIZE = 16
MHOD_STRING_DATA_OFFSET = 0x28

SPLPREF_BODY_SIZE = 132

SPL_RULE_DATA_SIZE = 0x44

MHOD52_BODY_HEADER_SIZE = 48
MHOD53_BODY_HEADER_SIZE = 16
MHOD53_ENTRY_SIZE = 12

MHOD100_POSITION_BODY_SIZE = 20

SORT_TITLE = 0x03
SORT_ALBUM = 0x04
SORT_ARTIST = 0x05
SORT_GENRE = 0x07
SORT_COMPOSER = 0x12
SORT_SHOW = 0x1D
SORT_SEASON = 0x1E
SORT_EPISODE = 0x1F
SORT_ALBUM_ARTIST = 0x23

CHAPTER_PREAMBLE_SIZE = 12
SEAN_ATOM = b'sean'
CHAP_ATOM = b'chap'
NAME_ATOM = b'name'
HEDR_ATOM = b'hedr'
HEDR_SIZE = 28

MHOD_FIELDS: list[FieldDef] = [
    _u32("mhod_type", 0x0C, section_type=_S, required=True),
    _u32("unk0x10", 0x10, section_type=_S),
    _u32("unk0x14", 0x14, section_type=_S),
]


STRING_MHOD_TYPES = (
    set(range(1, 15))
    | set(range(18, 32))
    | set(range(33, 45))
    | set(range(200, 205))
    | {300}
)

PODCAST_URL_MHOD_TYPES = {15, 16}

CHAPTER_DATA_MHOD_TYPES = {17}

BINARY_BLOB_MHOD_TYPES = {32}

NON_STRING_MHOD_TYPES = {50, 51, 52, 53, 55, 100, 102}


def write_mhod_header(mhod_type: int, total_length: int,
                      unk0x10: int = 0, unk0x14: int = 0) -> bytes:
    """Build the 24-byte MHOD common header.

    This is the shared pattern used by every MHOD writer — string,
    SPL, index, position, etc.

    Args:
        mhod_type: MHOD type ID (e.g. 1, 50, 51, 52, 53, 100, 102).
        total_length: Total length of the complete MHOD chunk
            (header + body).
        unk0x10: Unknown field at offset 0x10 (preserved from parser).
        unk0x14: Unknown field at offset 0x14 (preserved from parser).

    Returns:
        24-byte packed header.
    """
    return struct.pack(
        '<4sIIIII',
        b'mhod',
        MHOD_HEADER_SIZE,
        total_length,
        mhod_type,
        unk0x10,
        unk0x14,
    )


def mhod_string_encoding(data, offset) -> int:
    """Position/encoding indicator at 0x18.
    1 (or 0) = UTF-16LE (standard iPod, little-endian strings).
    2 = UTF-8 (mobile-phone iTunesDBs, inversed endian).
    libgpod checks this same field to decide encoding."""
    return struct.unpack("<I", data[offset + 0x18:offset + 0x1C])[0]


def mhod_string_length(data, offset) -> int:
    """Byte length of string data at 0x1C."""
    return struct.unpack("<I", data[offset + 0x1C:offset + 0x20])[0]


def mhod_string_unk0x20(data, offset) -> int:
    """Opaque string-subheader value; all 80,504 Classic sample values are 1."""
    return struct.unpack("<I", data[offset + 0x20:offset + 0x24])[0]


def mhod_string_unk0x24(data, offset) -> int:
    """Opaque string-subheader value; all 80,504 Classic sample values are 0."""
    return struct.unpack("<I", data[offset + 0x24:offset + 0x28])[0]


def mhod_spl_live_update(data, body_offset) -> int:
    return data[body_offset]


def mhod_spl_check_rules(data, body_offset) -> int:
    return data[body_offset + 1]


def mhod_spl_check_limits(data, body_offset) -> int:
    return data[body_offset + 2]


def mhod_spl_limit_type(data, body_offset) -> int:
    return data[body_offset + 3]


def mhod_spl_limit_sort_raw(data, body_offset) -> int:
    """Raw limit sort byte at +0x04 (before reverse flag is applied)."""
    return data[body_offset + 4]


def mhod_spl_limit_value(data, body_offset) -> int:
    return struct.unpack("<I", data[body_offset + 8:body_offset + 12])[0]


def mhod_spl_match_checked_only(data, body_offset) -> int:
    return data[body_offset + 12]


def mhod_spl_reverse_sort(data, body_offset) -> int:
    """Reverse flag at +0x0D. If set, limitsort |= 0x80000000."""
    return data[body_offset + 13]


SPL_LIMIT_TYPE_MINUTES = 0x01
SPL_LIMIT_TYPE_MB = 0x02
SPL_LIMIT_TYPE_SONGS = 0x03
SPL_LIMIT_TYPE_HOURS = 0x04
SPL_LIMIT_TYPE_GB = 0x05

SPL_LIMIT_TYPE_MAP = {
    SPL_LIMIT_TYPE_MINUTES: "minutes",
    SPL_LIMIT_TYPE_MB: "MB",
    SPL_LIMIT_TYPE_SONGS: "songs",
    SPL_LIMIT_TYPE_HOURS: "hours",
    SPL_LIMIT_TYPE_GB: "GB",
}

SPL_LIMIT_SORT_RANDOM = 0x02
SPL_LIMIT_SORT_SONG_NAME = 0x03
SPL_LIMIT_SORT_ALBUM = 0x04
SPL_LIMIT_SORT_ARTIST = 0x05
SPL_LIMIT_SORT_GENRE = 0x07
SPL_LIMIT_SORT_MOST_RECENTLY_ADDED = 0x10
SPL_LIMIT_SORT_LEAST_RECENTLY_ADDED = 0x80000010
SPL_LIMIT_SORT_MOST_OFTEN_PLAYED = 0x14
SPL_LIMIT_SORT_LEAST_OFTEN_PLAYED = 0x80000014
SPL_LIMIT_SORT_MOST_RECENTLY_PLAYED = 0x15
SPL_LIMIT_SORT_LEAST_RECENTLY_PLAYED = 0x80000015
SPL_LIMIT_SORT_HIGHEST_RATING = 0x17
SPL_LIMIT_SORT_LOWEST_RATING = 0x80000017

SPL_LIMIT_SORT_MAP = {
    SPL_LIMIT_SORT_RANDOM: "random",
    SPL_LIMIT_SORT_SONG_NAME: "song_name",
    SPL_LIMIT_SORT_ALBUM: "album",
    SPL_LIMIT_SORT_ARTIST: "artist",
    SPL_LIMIT_SORT_GENRE: "genre",
    SPL_LIMIT_SORT_MOST_RECENTLY_ADDED: "most_recently_added",
    SPL_LIMIT_SORT_LEAST_RECENTLY_ADDED: "least_recently_added",
    SPL_LIMIT_SORT_MOST_OFTEN_PLAYED: "most_often_played",
    SPL_LIMIT_SORT_LEAST_OFTEN_PLAYED: "least_often_played",
    SPL_LIMIT_SORT_MOST_RECENTLY_PLAYED: "most_recently_played",
    SPL_LIMIT_SORT_LEAST_RECENTLY_PLAYED: "least_recently_played",
    SPL_LIMIT_SORT_HIGHEST_RATING: "highest_rating",
    SPL_LIMIT_SORT_LOWEST_RATING: "lowest_rating",
}


SLST_HEADER_SIZE = 136


def mhod_slst_magic(data, body_offset) -> bytes:
    return data[body_offset:body_offset + 4]


def mhod_slst_unk004(data, body_offset) -> int:
    return struct.unpack(">I", data[body_offset + 4:body_offset + 8])[0]


def mhod_slst_rule_count(data, body_offset) -> int:
    return struct.unpack(">I", data[body_offset + 8:body_offset + 12])[0]


def mhod_slst_conjunction(data, body_offset) -> int:
    """0=AND (match all), 1=OR (match any)."""
    return struct.unpack(">I", data[body_offset + 12:body_offset + 16])[0]


SPL_RULE_HEADER_SIZE = 56


def mhod_spl_rule_field(data, rule_offset) -> int:
    return struct.unpack(">I", data[rule_offset:rule_offset + 4])[0]


def mhod_spl_rule_action(data, rule_offset) -> int:
    return struct.unpack(">I", data[rule_offset + 4:rule_offset + 8])[0]


def mhod_spl_rule_data_length(data, rule_offset) -> int:
    return struct.unpack(">I", data[rule_offset + 0x34:rule_offset + 0x38])[0]


def mhod_spl_rule_from_value(data, data_offset) -> int:
    return struct.unpack(">Q", data[data_offset:data_offset + 8])[0]


def mhod_spl_rule_from_date(data, data_offset) -> int:
    """Signed 64-bit big-endian."""
    return struct.unpack(">q", data[data_offset + 8:data_offset + 16])[0]


def mhod_spl_rule_from_units(data, data_offset) -> int:
    return struct.unpack(">Q", data[data_offset + 16:data_offset + 24])[0]


def mhod_spl_rule_to_value(data, data_offset) -> int:
    return struct.unpack(">Q", data[data_offset + 24:data_offset + 32])[0]


def mhod_spl_rule_to_date(data, data_offset) -> int:
    """Signed 64-bit big-endian."""
    return struct.unpack(">q", data[data_offset + 32:data_offset + 40])[0]


def mhod_spl_rule_to_units(data, data_offset) -> int:
    return struct.unpack(">Q", data[data_offset + 40:data_offset + 48])[0]


def mhod_spl_rule_unk052(data, data_offset) -> int:
    return struct.unpack(">I", data[data_offset + 48:data_offset + 52])[0]


def mhod_spl_rule_unk056(data, data_offset) -> int:
    return struct.unpack(">I", data[data_offset + 52:data_offset + 56])[0]


def mhod_spl_rule_unk060(data, data_offset) -> int:
    return struct.unpack(">I", data[data_offset + 56:data_offset + 60])[0]


def mhod_spl_rule_unk064(data, data_offset) -> int:
    return struct.unpack(">I", data[data_offset + 60:data_offset + 64])[0]


def mhod_spl_rule_unk068(data, data_offset) -> int:
    return struct.unpack(">I", data[data_offset + 64:data_offset + 68])[0]


SPL_FIELD_MAP = {
    0x02: "Song Name",
    0x03: "Album",
    0x04: "Artist",
    0x05: "Bit Rate",
    0x06: "Sample Rate",
    0x07: "Year",
    0x08: "Genre",
    0x09: "Kind",
    0x0A: "Date Modified",
    0x0B: "Track Number",
    0x0C: "Size",
    0x0D: "Time",
    0x0E: "Comment",
    0x10: "Date Added",
    0x12: "Composer",
    0x16: "Plays",
    0x17: "Last Played",
    0x18: "Disc Number",
    0x19: "Rating",
    0x1D: "Checked",
    0x1F: "Compilation",
    0x23: "BPM",
    0x25: "Album Artwork",
    0x27: "Grouping",
    0x28: "Playlist",
    0x29: "Purchased",
    0x36: "Description",
    0x37: "Category",
    0x39: "Podcast",
    0x3C: "Media Kind",
    0x3E: "TV Show",
    0x3F: "Season Number",
    0x44: "Skips",
    0x45: "Last Skipped",
    0x47: "Album Artist",
    0x4E: "Sort Song Name",
    0x4F: "Sort Album",
    0x50: "Sort Artist",
    0x51: "Sort Album Artist",
    0x52: "Sort Composer",
    0x53: "Sort TV Show",
    0x5A: "Album Rating",
    0x59: "Video Rating",
    0x85: "Location",
    0x86: "Cloud Status",
    0x9A: "Favorite / Suggest Less",
    0x9C: "Album Favorite / Suggest Less",
    0x9F: "Work",
    0xA0: "Movement Name",
    0xA1: "Movement Number",
}

SPL_ACTION_MAP = {
    0x00000001: "is",
    0x00000010: "is greater than",
    0x00000020: "is greater than or equal to",
    0x00000040: "is less than",
    0x00000080: "is less than or equal to",
    0x00000100: "is in the range",
    0x00000200: "is in the last",
    0x00000400: "binary AND",
    0x00000800: "binary unknown1",
    0x01000001: "is (string)",
    0x01000002: "contains",
    0x01000004: "begins with",
    0x01000008: "ends with",
    0x02000001: "is not",
    0x02000010: "is not greater than",
    0x02000020: "is not greater than or equal to",
    0x02000040: "is not less than",
    0x02000080: "is not less than or equal to",
    0x02000100: "is not in the range",
    0x02000200: "is not in the last",
    0x02000400: "not binary AND",
    0x02000800: "binary unknown2",
    0x03000001: "is not (string)",
    0x03000002: "does not contain",
    0x03000004: "does not begin with",
    0x03000008: "does not end with",
}

SPL_DATE_RELATIVE_ACTION_IDS = {0x00000200, 0x02000200}

SPL_DATE_IDENTIFIER = 0x2DAE2DAE2DAE2DAE

SPLFT_STRING = 1
SPLFT_INT = 2
SPLFT_BOOLEAN = 3
SPLFT_DATE = 4
SPLFT_PLAYLIST = 5
SPLFT_UNKNOWN = 6
SPLFT_BINARY_AND = 7

SPL_FIELD_TYPE_MAP = {
    0x02: SPLFT_STRING,
    0x03: SPLFT_STRING,
    0x04: SPLFT_STRING,
    0x08: SPLFT_STRING,
    0x09: SPLFT_STRING,
    0x0E: SPLFT_STRING,
    0x12: SPLFT_STRING,
    0x27: SPLFT_STRING,
    0x36: SPLFT_STRING,
    0x37: SPLFT_STRING,
    0x3E: SPLFT_STRING,
    0x47: SPLFT_STRING,
    0x4E: SPLFT_STRING,
    0x4F: SPLFT_STRING,
    0x50: SPLFT_STRING,
    0x51: SPLFT_STRING,
    0x52: SPLFT_STRING,
    0x53: SPLFT_STRING,
    0x59: SPLFT_STRING,
    0x9F: SPLFT_STRING,
    0xA0: SPLFT_STRING,
    0x05: SPLFT_INT,
    0x06: SPLFT_INT,
    0x07: SPLFT_INT,
    0x0B: SPLFT_INT,
    0x0C: SPLFT_INT,
    0x0D: SPLFT_INT,
    0x16: SPLFT_INT,
    0x18: SPLFT_INT,
    0x19: SPLFT_INT,
    0x23: SPLFT_INT,
    0x3F: SPLFT_INT,
    0x44: SPLFT_INT,
    0x5A: SPLFT_INT,
    0x86: SPLFT_INT,
    0x9A: SPLFT_INT,
    0x9C: SPLFT_INT,
    0xA1: SPLFT_INT,
    0x0A: SPLFT_DATE,
    0x10: SPLFT_DATE,
    0x17: SPLFT_DATE,
    0x45: SPLFT_DATE,
    0x1D: SPLFT_BOOLEAN,
    0x25: SPLFT_BOOLEAN,
    0x1F: SPLFT_BOOLEAN,
    0x29: SPLFT_BOOLEAN,
    0x39: SPLFT_INT,
    0x28: SPLFT_PLAYLIST,
    0x85: SPLFT_BINARY_AND,
    0x3C: SPLFT_INT,
}

SPL_HOST_STRING_FIELD_KEYS: dict[int, str] = {
    0x02: "Title",
    0x03: "Album",
    0x04: "Artist",
    0x08: "Genre",
    0x09: "filetype",
    0x0E: "Comment",
    0x12: "Composer",
    0x27: "Grouping",
    0x36: "Description Text",
    0x37: "Category",
    0x3E: "Show",
    0x47: "Album Artist",
    0x4E: "Sort Title",
    0x4F: "Sort Album",
    0x50: "Sort Artist",
    0x51: "Sort Album Artist",
    0x52: "Sort Composer",
    0x53: "Sort Show",
}

SPL_HOST_INT_FIELD_KEYS: dict[int, str] = {
    0x05: "bitrate",
    0x06: "sample_rate_1",
    0x07: "year",
    0x0B: "track_number",
    0x0C: "size",
    0x0D: "length",
    0x16: "play_count_1",
    0x18: "disc_number",
    0x19: "rating",
    0x23: "bpm",
    0x39: "podcast_flag",
    0x3C: "media_type",
    0x3F: "season_number",
    0x44: "skip_count",
}

SPL_HOST_DATE_FIELD_KEYS: dict[int, str] = {
    0x0A: "last_modified",
    0x10: "date_added",
    0x17: "last_played",
    0x45: "last_skipped",
}

SPL_HOST_BOOLEAN_FIELD_KEYS: dict[int, str] = {
    0x1D: "checked_flag",
    0x1F: "compilation_flag",
    0x25: "has_artwork",
    0x29: "purchased_flag",
}

SPL_HOST_BINARY_AND_FIELD_KEYS: dict[int, str] = {
    0x85: "location_kind",
}

SPL_HOST_EVALUABLE_FIELD_IDS = frozenset(
    {
        *SPL_HOST_STRING_FIELD_KEYS,
        *SPL_HOST_INT_FIELD_KEYS,
        *SPL_HOST_DATE_FIELD_KEYS,
        *SPL_HOST_BOOLEAN_FIELD_KEYS,
        *SPL_HOST_BINARY_AND_FIELD_KEYS,
        0x28,
    }
)

SPL_AUTHORABLE_FIELD_IDS = SPL_HOST_EVALUABLE_FIELD_IDS - frozenset({
    0x39,
    0x3E,
    0x3F,
})

SPL_CHOICE_FIELD_IDS = frozenset({0x28, 0x3C, 0x85, 0x86, 0x9A, 0x9C})

SPL_CHOICE_VALUE_MAP: dict[int, tuple[tuple[int, str], ...]] = {
    0x9A: (
        (2, "Favorite"),
        (3, "Suggest Less"),
        (0, "None"),
    ),
    0x9C: (
        (2, "Favorite"),
        (3, "Suggest Less"),
        (0, "None"),
    ),
    0x86: (
        (2, "Matched"),
        (1, "Purchased"),
        (3, "Uploaded"),
        (4, "Ineligible"),
        (5, "Removed"),
        (6, "Error"),
        (7, "Duplicate"),
        (8, "Apple Music"),
        (9, "No Longer Available"),
        (10, "Not Uploaded"),
    ),
    0x85: (
        (1, "on this computer"),
        (2, "iCloud"),
    ),
    0x3C: (
        (0x00000001, "Music"),
        (0x00000020, "Music Video"),
        (0x00000002, "Movie"),
        (0x00000040, "TV Show"),
        (0x00000004, "Podcast"),
        (0x00000008, "Audiobook"),
        (0x00100000, "Voice Memo"),
        (0x00010000, "iTunes Extras"),
    ),
}

SPL_CHOICE_UNKNOWN_LABELS: dict[int, tuple[str, ...]] = {
    0x3C: ("Home Video",),
}

SPL_DATE_UNITS_MAP = {
    1: "seconds",
    60: "minutes",
    3600: "hours",
    86400: "days",
    604800: "weeks",
    2628000: "months",
}


def spl_get_field_type(field_id: int) -> int:
    """Determine SPL field type from field ID (equivalent to libgpod's itdb_splr_get_field_type)."""
    return SPL_FIELD_TYPE_MAP.get(field_id, SPLFT_UNKNOWN)


SORT_TYPE_MAP = {
    0x03: "title",
    0x04: "album",
    0x05: "artist",
    0x07: "genre",
    0x12: "composer",
    0x1D: "show",
    0x1E: "season_number",
    0x1F: "episode_number",
    0x23: "album_artist",
    0x24: "artist_nosort",
}


def mhod52_sort_type(data, body_offset) -> int:
    return struct.unpack("<I", data[body_offset:body_offset + 4])[0]


def mhod52_count(data, body_offset) -> int:
    return struct.unpack("<I", data[body_offset + 4:body_offset + 8])[0]


def mhod53_sort_type(data, body_offset) -> int:
    return struct.unpack("<I", data[body_offset:body_offset + 4])[0]


def mhod53_count(data, body_offset) -> int:
    return struct.unpack("<I", data[body_offset + 4:body_offset + 8])[0]


def mhod100_position(data, body_offset) -> int:
    return struct.unpack("<I", data[body_offset:body_offset + 4])[0]
