"""CLI del módulo iPod.

Uso (el iPod se descubre solo revalidando el montaje con write_guard)::

    python -m cicada ipod backup [--full]
    python -m cicada ipod restore <archivo>
    python -m cicada ipod list-backups

Todas las operaciones pasan por :mod:`cicada.ipod.device.write_guard` y
:mod:`cicada.ipod.device.backup`.
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from cicada.ipod.device import backup as backup_mod
from cicada.ipod.device.backup import BackupError, BackupMode
from cicada.ipod.device.write_guard import WriteGuardError, resolve_mount


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cicada ipod", description="Gestión del iPod")
    sub = parser.add_subparsers(dest="command", required=True)

    p_backup = sub.add_parser("backup", help="Crea un backup del iPod")
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
    p_eject.add_argument(
        "--force",
        action="store_true",
        help="Fuerza la expulsión aunque un proceso la rechace (decisión explícita)",
    )

    p_id = sub.add_parser("identify", help="Muestra la identidad del iPod montado")
    p_id.add_argument(
        "--usb",
        action="store_true",
        help="Permite leer el FireWireGUID por USB si no está en disco (Etapa 2d)",
    )
    return parser


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


def _cmd_identify(args: argparse.Namespace) -> int:
    from cicada.ipod.device.device_info import read_device_info
    mount = resolve_mount()
    info = read_device_info(mount, use_usb=args.usb)
    print(f"Modelo    : {info.family or '?'} {info.generation or ''} {info.color or ''}".rstrip())
    print(f"Capacidad : {info.capacity or '?'}")
    print(f"Firma     : {info.checksum.name if info.checksum else '?'}")
    print(f"GUID      : {info.firewire_guid or '(no resuelto)'}")
    print(f"Procedencia GUID: {info.guid_provenance or 'ninguna'}"
          + ("  [write-safe]" if info.guid_is_write_safe else "  [NO write-safe]"))
    print(f"Serial    : {info.serial or '?'}")
    print(f"Parcial   : {info.partial}")
    if info.usb_error:
        print(f"USB error : {info.usb_error}")
    return 0 if not info.partial else 1


def _cmd_eject(args: argparse.Namespace) -> int:
    from cicada.ipod.device.eject import eject_ipod
    mount = resolve_mount()
    result = eject_ipod(mount, force=args.force)
    print(result.message)
    if not result.ejected and result.blockers:
        for b in result.blockers:
            print(f"  PID {b.pid}  {b.friendly_name} ({b.name})")
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


_HANDLERS = {
    "backup": _cmd_backup,
    "restore": _cmd_restore,
    "list-backups": _cmd_list,
    "clean-foreign": _cmd_clean_foreign,
    "eject": _cmd_eject,
    "identify": _cmd_identify,
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


if __name__ == "__main__":
    sys.exit(main())
