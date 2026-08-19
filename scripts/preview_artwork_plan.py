"""Preview de artwork ANTES de sincronizar de verdad — no escribe nada en el
iPod (create_plan() es dry-run puro, todo el output va a un staging temporal
off-device). Uso:

    python scripts/preview_artwork_plan.py "/ruta/cancion1.mp3" "/ruta/cancion2.m4a" ...

Imprime, por cada canción: si se encontró carátula embebida, y si
build_artwork_assets() la codificó con éxito (img_id asignado) o la saltó.
"""
import sys
from pathlib import Path

from cicada.ipod.db.coordinator.plan import create_plan
from cicada.ipod.db.models import TrackInfo
from cicada.ipod.device.device_info import read_device_info
from cicada.ipod.device.write_guard import resolve_mount


def main() -> int:
    paths = sys.argv[1:]
    if not paths:
        print("Uso: preview_artwork_plan.py <archivo1> <archivo2> ...", file=sys.stderr)
        return 1

    mount = resolve_mount()
    dev = read_device_info(mount)
    print(f"iPod montado en: {mount}")
    print(f"GUID: {dev.firewire_guid}  write-safe: {dev.guid_is_write_safe}\n")

    tracks = []
    for i, p in enumerate(paths):
        src = Path(p)
        if not src.is_file():
            print(f"AVISO: no existe {src}", file=sys.stderr)
            continue
        tracks.append(
            TrackInfo(
                title=src.stem,
                location=f":iPod_Control:Music:F00:preview_{i}.mp3",
                db_track_id=90000 + i,
                source_path=str(src),
            )
        )

    if not tracks:
        print("Ningún archivo válido.", file=sys.stderr)
        return 1

    plan = create_plan(mount, tracks, device_info=dev)

    print(f"artwork_touched        : {plan.artwork_touched}")
    print(f"artwork_tracks_count   : {plan.artwork_tracks_count}  (de {len(tracks)} analizadas)")
    print(f"artwork_skipped_count  : {plan.artwork_skipped_count}")
    print()
    for t in tracks:
        status = f"img_id={t.mhii_link}, {t.artwork_size} bytes fuente" if t.mhii_link else "SIN carátula (no se encontró o no se pudo decodificar)"
        print(f"  {t.title:<40} -> {status}")

    print(f"\nStaging (no se escribió nada en el iPod): {plan.staging_dir}")
    if plan.artwork_touched:
        print(f"ArtworkDB de staging: {plan.staging_dir / 'Artwork' / 'ArtworkDB'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
