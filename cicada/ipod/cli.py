"""CLI del módulo iPod.

Uso::

    python -m cicada ipod status [--usb]
    python -m cicada ipod tracks [--json]
    python -m cicada ipod plan --tracks-file <pistas.json>
    python -m cicada ipod sync --tracks-file <pistas.json> [--ack-consent]
    python -m cicada ipod consent {show,grant,revoke}
    python -m cicada ipod backup [--full]
    python -m cicada ipod restore <archivo.tar.zst>
    python -m cicada ipod list-backups
    python -m cicada ipod eject [--force]
    python -m cicada ipod sync-playback [--dry-run]

Todas las operaciones sobre el disco pasan por :mod:`cicada.ipod.device.write_guard`,
:mod:`cicada.ipod.db.coordinator.plan` y :mod:`cicada.ipod.db.coordinator.apply`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from cicada.ipod.db.coordinator.apply import ApplyError, apply
from cicada.ipod.db.coordinator.consent import (
    ConsentRequiredError,
    get_consent_record,
    has_music_app_consent,
    record_music_app_consent,
    revoke_music_app_consent,
)
from cicada.ipod.db.coordinator.plan import PlanError, create_plan
from cicada.ipod.db.parser import load_ipod_library
from cicada.ipod.db.models import TrackInfo
from cicada.ipod.device import backup as backup_mod
from cicada.ipod.device.backup import BackupError, BackupMode
from cicada.ipod.device.device_info import read_device_info
from cicada.ipod.device.eject import eject_ipod
from cicada.ipod.device.write_guard import WriteGuardError, resolve_mount


def _load_tracks_from_file(path: str) -> list[TrackInfo]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("El archivo JSON debe contener una lista de objetos track.")
    tracks: list[TrackInfo] = []
    for d in data:
        tracks.append(
            TrackInfo(
                title=d.get("Title") or d.get("title") or "Unknown Title",
                artist=d.get("Artist") or d.get("artist") or "",
                album=d.get("Album") or d.get("album") or "",
                album_artist=d.get("Album Artist") or d.get("album_artist") or "",
                genre=d.get("Genre") or d.get("genre") or "",
                composer=d.get("Composer") or d.get("composer") or "",
                comment=d.get("Comment") or d.get("comment") or "",
                year=int(d.get("year") or d.get("Year") or 0),
                track_number=int(d.get("track_number") or d.get("TrackNumber") or 0),
                disc_number=int(d.get("disc_number") or d.get("DiscNumber") or 0),
                bitrate=int(d.get("bitrate") or d.get("Bitrate") or 0),
                length=int(d.get("length") or d.get("Length") or 0),
                size=int(d.get("size") or d.get("Size") or 0),
                date_added=int(d.get("date_added") or 0),
                last_modified=int(d.get("last_modified") or 0),
                play_count=int(d.get("play_count") or 0),
                rating=int(d.get("rating") or 0),
                last_played=int(d.get("last_played") or 0),
                location=d.get("Location") or d.get("location") or "",
                db_track_id=int(d.get("db_track_id") or d.get("dbid") or 0),
            )
        )
    return tracks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cicada ipod", description="Gestión y sincronización del iPod")
    sub = parser.add_subparsers(dest="command", required=True)

    # 1. status / identify
    p_id = sub.add_parser("status", aliases=["identify"], help="Muestra la identidad y estado del iPod montado")
    p_id.add_argument("--usb", action="store_true", help="Permite leer el FireWireGUID por USB si no está en disco")

    # 2. tracks
    p_tr = sub.add_parser("tracks", help="Lista las pistas en la base de datos actual del iPod")
    p_tr.add_argument("--json", action="store_true", help="Salida en formato JSON")

    # 3. plan
    p_plan = sub.add_parser("plan", help="Genera un plan dry-run en staging off-device")
    p_plan.add_argument("--tracks-file", required=True, help="Ruta al archivo JSON con la lista de pistas")

    # 4. sync / apply
    p_sync = sub.add_parser("sync", aliases=["apply"], help="Ejecuta la sincronización transaccional sobre el iPod")
    p_sync.add_argument("--tracks-file", required=True, help="Ruta al archivo JSON con la lista de pistas")
    p_sync.add_argument("--ack-consent", "--yes", "-y", action="store_true", help="Acepta la advertencia de Music.app")

    # 5. consent
    p_consent = sub.add_parser("consent", help="Consulta u otorga consentimiento para la advertencia de Music.app")
    p_consent.add_argument("action", choices=["show", "grant", "revoke"], help="Acción de consentimiento")

    # 6. backup / restore / list-backups
    p_backup = sub.add_parser("backup", help="Crea un snapshot de seguridad del iPod")
    p_backup.add_argument(
        "--full",
        action="store_true",
        help="Árbol completo incluyendo Music/ (por defecto: solo iTunes/ y Device/)",
    )

    p_restore = sub.add_parser("restore", help="Restaura un backup sobre el iPod")
    p_restore.add_argument("archivo", help="Ruta del .tar.zst a restaurar")

    sub.add_parser("list-backups", help="Lista los backups existentes")

    sub.add_parser(
        "clean-foreign",
        help="Elimina el iOpenPodSysInfoAuthority ajeno del dispositivo (vía write_guard)",
    )

    p_eject = sub.add_parser("eject", help="Expulsa el iPod de forma segura")
    p_eject.add_argument("--force", action="store_true", help="Fuerza la expulsión aunque un proceso la rechace")

    p_syncpb = sub.add_parser(
        "sync-playback",
        help="Escanea contadores/rating del iPod y actualiza la línea base local (~/.cicada/ipod.db)",
    )
    p_syncpb.add_argument("--dry-run", action="store_true", help="Solo muestra el informe, no persiste la línea base")

    return parser


def _cmd_status(args: argparse.Namespace) -> int:
    mount = resolve_mount()
    info = read_device_info(mount, use_usb=args.usb)
    has_consent = has_music_app_consent(info.firewire_guid) if info.firewire_guid else False

    print(f"Montaje   : {mount}")
    print(f"Modelo    : {info.family or '?'} {info.generation or ''} {info.color or ''}".rstrip())
    print(f"Capacidad : {info.capacity or '?'}")
    print(f"Firma     : {info.checksum.name if info.checksum else '?'}")
    print(f"GUID      : {info.firewire_guid or '(no resuelto)'}")
    print(f"Procedencia: {info.guid_provenance or 'ninguna'}"
          + ("  [write-safe]" if info.guid_is_write_safe else "  [NO write-safe]"))
    print(f"Consentimiento Music.app: {'Otorgado' if has_consent else 'Pendiente'}")
    print(f"Serial    : {info.serial or '?'}")
    if info.usb_error:
        print(f"USB error : {info.usb_error}")
    return 0 if not info.partial else 1


def _cmd_tracks(args: argparse.Namespace) -> int:
    mount = resolve_mount()
    itunes_dir = mount / "iPod_Control" / "iTunes"
    cdb_file = itunes_dir / "iTunesCDB"
    db_file = itunes_dir / "iTunesDB"
    target = cdb_file if cdb_file.is_file() else db_file

    if not target.is_file():
        print("No se encontró base de datos en el iPod.", file=sys.stderr)
        return 1

    lib = load_ipod_library(str(target), mount=str(mount))
    if not lib:
        print("No se pudo leer la biblioteca del iPod.", file=sys.stderr)
        return 1

    tracks = lib.get("mhlt", [])
    if args.json:
        print(json.dumps(tracks, indent=2, ensure_ascii=False))
    else:
        print(f"Total pistas: {len(tracks)}")
        for i, t in enumerate(tracks, 1):
            title = t.get("Title", "Unknown")
            artist = t.get("Artist", "Unknown")
            album = t.get("Album", "")
            print(f"  {i:3d}. {artist} - {title} ({album})")
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    mount = resolve_mount()
    dev = read_device_info(mount)
    tracks = _load_tracks_from_file(args.tracks_file)

    print(f"Generando plan dry-run para {len(tracks)} pistas...")
    plan = create_plan(mount, tracks, device_info=dev)

    print("\n--- RESUMEN DEL PLAN ---")
    print(f"GUID          : {plan.guid}")
    print(f"Total pistas  : {plan.tracks_count}")
    print(f"Write-safe    : {plan.write_safe}")
    print(f"Consentimiento: {'REQUERIDO' if plan.consent_needed else 'Ya otorgado'}")
    print(f"Staging dir   : {plan.staging_dir}")
    print("\nArtefactos generados en staging:")
    for rel, (size, sha) in plan.artifacts.items():
        print(f"  - {rel:<55} {size:>8} bytes  ({sha[:12]}...)")
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    mount = resolve_mount()
    dev = read_device_info(mount)
    tracks = _load_tracks_from_file(args.tracks_file)

    plan = create_plan(mount, tracks, device_info=dev)

    if plan.consent_needed and not args.ack_consent:
        print("\nADVERTENCIA: La primera escritura en el iPod invalidará la compatibilidad con Music.app de Apple.", file=sys.stderr)
        print("Pasa --ack-consent (o -y) para confirmar y continuar.", file=sys.stderr)
        return 1

    def on_progress(msg: str, frac: float):
        percent = int(frac * 100)
        print(f"[{percent:3d}%] {msg}")

    print(f"Iniciando sincronización transaccional ({len(tracks)} pistas)...")
    res = apply(plan, mount=mount, device_info=dev, consent_ack=args.ack_consent, on_progress=on_progress)

    if res.success:
        print("\nSincronización completada con éxito.")
        if res.backup_path:
            print(f"Backup de seguridad: {res.backup_path}")
        return 0
    else:
        print(f"\nERROR: Falló la sincronización: {res.error}", file=sys.stderr)
        if res.restored_from_backup:
            print("El iPod fue restaurado automáticamente a su estado previo exacto.", file=sys.stderr)
        return 1


def _cmd_consent(args: argparse.Namespace) -> int:
    mount = resolve_mount()
    dev = read_device_info(mount)
    guid = dev.firewire_guid
    if not guid:
        print("No se pudo determinar el GUID del dispositivo.", file=sys.stderr)
        return 1

    if args.action == "show":
        rec = get_consent_record(guid)
        if rec and rec.music_app_ack:
            print(f"Consentimiento OTORGADO para GUID {guid}")
            print(f"Aprobado en        : {rec.acked_at}")
            print(f"Primera escritura  : {rec.first_write_committed_at or 'Pendiente'}")
        else:
            print(f"Consentimiento NO otorgado para GUID {guid}")
    elif args.action == "grant":
        record_music_app_consent(guid)
        print(f"Consentimiento de Music.app registrado con éxito para GUID {guid}")
    elif args.action == "revoke":
        revoke_music_app_consent(guid)
        print(f"Consentimiento revocado para GUID {guid}")
    return 0


def _cmd_backup(args: argparse.Namespace) -> int:
    mount = resolve_mount()
    mode = BackupMode.FULL if args.full else BackupMode.DB_ONLY
    archive = backup_mod.create_backup(mount, mode)
    print(f"Backup creado: {archive}")
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    mount = resolve_mount()
    backup_mod.restore_backup(args.archivo, mount)
    print(f"Restaurado {args.archivo} en {mount}")
    return 0


def _cmd_clean_foreign(_args: argparse.Namespace) -> int:
    from cicada.ipod.device.authority import clean_foreign_authority
    mount = resolve_mount()
    removed = clean_foreign_authority(mount)
    if removed:
        print(f"Eliminado iOpenPodSysInfoAuthority de {mount}")
    else:
        print("No había iOpenPodSysInfoAuthority en el dispositivo.")
    return 0


def _cmd_eject(args: argparse.Namespace) -> int:
    mount = resolve_mount()
    result = eject_ipod(mount, force=args.force)
    print(result.message)
    if not result.ejected and result.blockers:
        for b in result.blockers:
            label = b.friendly_name if b.friendly_name == b.name else f"{b.friendly_name} ({b.name})"
            print(f"  PID {b.pid}  {label}")
        return 1
    return 0 if result.ejected else 1


def _cmd_list(_args: argparse.Namespace) -> int:
    infos = backup_mod.list_backups()
    if not infos:
        print("No hay backups.")
        return 0
    for info in infos:
        mb = info.size_bytes / (1024 * 1024)
        print(f"{info.timestamp}  {info.mode.value:<8}  {mb:7.2f} MB  {info.guid}  {info.path}")
    return 0


def _cmd_sync_playback(args: argparse.Namespace) -> int:
    from cicada.ipod.sync.bidirectional import compute_playback_deltas, sync_playback_stats
    from cicada.ipod.sync.state import SyncStateDB

    mount = resolve_mount()
    dev = read_device_info(mount)
    if not dev.firewire_guid:
        print("No se pudo identificar el GUID del iPod.", file=sys.stderr)
        return 1

    if args.dry_run:
        # Puro SELECT (get_all_playback_states/get_track_map): no requiere
        # el device pre-registrado, así que un dry-run no escribe nada.
        report = compute_playback_deltas(mount, SyncStateDB(), dev.firewire_guid)
    else:
        report = sync_playback_stats(mount, dev)

    print(f"Pistas escaneadas : {report.total_tracks_scanned}")
    print(f"Pistas con cambios: {len(report.tracks_with_deltas)}")
    print(f"Reproducciones +  : {report.total_delta_plays}")
    print(f"Saltos +          : {report.total_delta_skips}")
    print(f"Ratings cambiados : {report.ratings_updated_count}")
    if args.dry_run:
        print("(dry-run: línea base NO actualizada)")
    return 0


_HANDLERS = {
    "status": _cmd_status,
    "identify": _cmd_status,
    "tracks": _cmd_tracks,
    "plan": _cmd_plan,
    "sync": _cmd_sync,
    "apply": _cmd_sync,
    "consent": _cmd_consent,
    "backup": _cmd_backup,
    "restore": _cmd_restore,
    "list-backups": _cmd_list,
    "clean-foreign": _cmd_clean_foreign,
    "eject": _cmd_eject,
    "sync-playback": _cmd_sync_playback,
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _HANDLERS[args.command](args)
    except WriteGuardError as exc:
        print(f"error (guardia de escritura): {exc}", file=sys.stderr)
        return 2
    except BackupError as exc:
        print(f"error (backup): {exc}", file=sys.stderr)
        return 3
    except (PlanError, ApplyError, ConsentRequiredError) as exc:
        print(f"error (coordinador): {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
