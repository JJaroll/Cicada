"""Locations.itdb writer — iPod file path mapping database.

Maps track PIDs to their physical file locations on the iPod filesystem.

Schema:
    base_location: single row with root path "iPod_Control/Music"
    location: one row per track, mapping item_pid → "Fxx/ABCD.mp3"

Reference: libgpod itdb_sqlite.c mk_Locations()
"""

import logging
import time

from cicada.ipod.db.shared.constants import FILETYPE_CODES
from cicada.ipod.db.models import TrackInfo

from ._helpers import open_db, unix_to_coredata
from ._helpers import s64 as _s64

logger = logging.getLogger(__name__)


LOCATION_TYPE_FILE = 0x46494C45

_EXTENSION_CODES = FILETYPE_CODES

_KIND_ID = {
    'mp3': 1,
    'aac': 3,
    'm4a': 3,
    'm4p': 2,
    'm4b': 3,
    'm4v': 3,
    'mp4': 3,
    'wav': 1,
    'aif': 1,
    'aiff': 1,
    'alac': 3,
}


def _ipod_path_to_location(ipod_path: str) -> str:
    """Convert iPod colon-separated path to slash-based location.

    Input:  ":iPod_Control:Music:F04:ZEUN.mp3"
    Output: "F04/ZEUN.mp3"

    The location field stores the path relative to the base_location
    ("iPod_Control/Music"), using forward slashes.
    """
    parts = ipod_path.strip(':').split(':')
    if len(parts) >= 4 and parts[0] == 'iPod_Control' and parts[1] == 'Music':
        return '/'.join(parts[2:])
    elif len(parts) >= 2:
        return '/'.join(parts[-2:])
    else:
        return ipod_path.strip(':').replace(':', '/')


_LOCATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS base_location (
    id INTEGER NOT NULL,
    path TEXT,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS location (
    item_pid INTEGER NOT NULL,
    sub_id INTEGER NOT NULL DEFAULT 0,
    base_location_id INTEGER DEFAULT 0,
    location_type INTEGER,
    location TEXT,
    extension INTEGER,
    kind_id INTEGER DEFAULT 0,
    date_created INTEGER DEFAULT 0,
    file_size INTEGER DEFAULT 0,
    file_creator INTEGER,
    file_type INTEGER,
    num_dir_levels_file INTEGER,
    num_dir_levels_lib INTEGER,
    PRIMARY KEY (item_pid, sub_id)
);
"""


def write_locations_itdb(
    path: str,
    tracks: list[TrackInfo],
) -> None:
    """Write Locations.itdb SQLite database.

    Args:
        path: Output file path.
        tracks: List of TrackInfo objects (with db_track_id and location set).
    """
    conn, cur = open_db(path)

    cur.executescript(_LOCATIONS_SCHEMA)

    cur.execute(
        "INSERT INTO base_location (id, path) VALUES (1, 'iPod_Control/Music')"
    )

    now = int(time.time())

    for track in tracks:
        location = _ipod_path_to_location(track.location)
        ft = track.filetype.lower()
        extension = _EXTENSION_CODES.get(ft, _EXTENSION_CODES.get('mp3', 0x4D503320))
        kind_id = _KIND_ID.get(ft, 0)

        date_added = track.date_added or now
        date_cd = unix_to_coredata(date_added)

        cur.execute(
            """INSERT INTO location (
                item_pid, sub_id, base_location_id, location_type,
                location, extension, kind_id, date_created, file_size,
                file_creator, file_type,
                num_dir_levels_file, num_dir_levels_lib
            ) VALUES (?, 0, 1, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)""",
            (
                _s64(track.db_track_id), LOCATION_TYPE_FILE,
                location, extension, kind_id,
                date_cd, track.size,
            )
        )

    conn.commit()
    conn.close()

    logger.info("Wrote Locations.itdb: %d locations", len(tracks))
