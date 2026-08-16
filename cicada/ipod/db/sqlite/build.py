"""Construcción de las bases SQLite del iPod en staging — código propio.

Reimplementa la orquestación de `sqlite_writer.write_sqlite_databases` (que
estaba enredada con el stack de escritura-al-dispositivo), produciendo el
`iTunes Library.itlp/` en un directorio **off-device**. Los builders individuales
(`write_library_itdb`, etc.) son vendorizados de iOpenPod (paquete 5).

La instalación al volumen es del coordinador (Etapa 2c) vía `safe_write`.

`time_context`: el MISMO con el que se leyó la base. Imprescindible para que
`Dynamic.item_stats.date_played` (last_played) no se desplace por la zona horaria
(ver §0.3 / hallazgo de fechas de la Etapa 2a).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from cicada.ipod.db.shared.device_time import (
    DeviceTimeContext,
    use_device_time_context,
)
from cicada.ipod.db.models import PlaylistInfo, TrackInfo
from cicada.ipod.device.capabilities import DeviceCapabilities
from cicada.ipod.device.checksum import ChecksumType

from .cbk_writer import write_locations_cbk
from .dynamic_writer import write_dynamic_itdb
from .extras_writer import write_extras_itdb
from .genius_writer import write_genius_itdb
from .library_writer import write_library_itdb
from .locations_writer import write_locations_itdb

__all__ = ["build_sqlite_databases", "ITLP_FILES"]

#: Los archivos que componen el itlp/ (para install/rotación del coordinador).
ITLP_FILES = (
    "Library.itdb", "Locations.itdb", "Dynamic.itdb",
    "Extras.itdb", "Genius.itdb", "Locations.itdb.cbk",
)


def build_sqlite_databases(
    dest_itlp: str | Path,
    tracks: list[TrackInfo],
    *,
    firewire_id: bytes,
    checksum: ChecksumType,
    capabilities: Optional[DeviceCapabilities] = None,
    playlists: Optional[list[PlaylistInfo]] = None,
    smart_playlists: Optional[list[PlaylistInfo]] = None,
    db_pid: int = 0,
    master_playlist_name: str = "iPod",
    time_context: Optional[DeviceTimeContext] = None,
) -> dict:
    """Construye las 5 `.itdb` + `.cbk` en ``dest_itlp`` (off-device).

    Devuelve ``{"itlp": Path, "playlist_pids": ...}``. No toca el dispositivo.
    """
    if not firewire_id or len(firewire_id) < 8:
        raise ValueError("firewire_id de 8+ bytes requerido para firmar el .cbk")
    dest = Path(dest_itlp)
    dest.mkdir(parents=True, exist_ok=True)

    ctx = time_context or DeviceTimeContext.utc()
    with use_device_time_context(ctx):
        lib_path = dest / "Library.itdb"
        playlist_pids = write_library_itdb(
            path=str(lib_path), tracks=tracks, playlists=playlists,
            smart_playlists=smart_playlists, master_playlist_name=master_playlist_name,
            db_pid=db_pid,
        )
        loc_path = dest / "Locations.itdb"
        write_locations_itdb(path=str(loc_path), tracks=tracks)
        write_dynamic_itdb(path=str(dest / "Dynamic.itdb"), tracks=tracks,
                           playlist_pids=playlist_pids)
        write_extras_itdb(path=str(dest / "Extras.itdb"), tracks=tracks)
        write_genius_itdb(path=str(dest / "Genius.itdb"))

        # .cbk (checksums SHA1 de bloque + cabecera HASHAB) — firmado sobre Locations.itdb.
        write_locations_cbk(
            cbk_path=str(dest / "Locations.itdb.cbk"),
            locations_itdb_path=str(loc_path),
            checksum_type=checksum,
            firewire_id=firewire_id,
            ipod_path=str(dest),
        )

    return {"itlp": dest, "playlist_pids": playlist_pids}
