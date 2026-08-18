"""Expulsión segura del iPod, con identificación del proceso que bloquea.

Lección del dispositivo real: la expulsión puede ser **rechazada de forma
persistente** por otro proceso (en macOS, ``AMPDevicesAgent`` — el servicio de
Música). En vez de fallar con un booleano mudo, esta función:

- hace **flush** antes de intentar (vía :mod:`durability`),
- **nunca fuerza por defecto** (``force`` es decisión explícita del usuario),
- usa **timeout** en todo subproceso (no se cuelga),
- y devuelve **quién bloquea** (:class:`Blocker`) al llamador, con un nombre
  entendible (``friendly_name``) para poder decir *"Música está usando el iPod,
  ciérralo e intenta de nuevo"*.

Estado por plataforma:
- **macOS**: implementado (parser del disidente de ``diskutil`` + fallback ``lsof``).
- **Linux**: implementado (``umount`` no forzado + bloqueadores vía ``lsof``).
- **Windows**: **esbozado** — devuelve un resultado honesto ("no se pueden
  identificar procesos bloqueadores en Windows todavía"). Pendiente en VENDORED.md.

Módulo propio de Cicada (no vendorizado): iOpenPod expulsa pero NO identifica al
proceso que bloquea.
"""
from __future__ import annotations

import logging
import plistlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cicada.ipod.device import durability

logger = logging.getLogger(__name__)

__all__ = [
    "Blocker",
    "EjectResult",
    "FRIENDLY_NAMES",
    "eject_ipod",
]

#: Binario conocido → nombre entendible por el usuario. Sin coincidencia, se usa
#: el nombre crudo del binario.
FRIENDLY_NAMES: dict[str, str] = {
    "AMPDevicesAgent": "Música",
    "AMPLibraryAgent": "Música",
    "Music": "Música",
    "iTunes": "Música",
    "Finder": "Finder",
    "mds": "Spotlight",
    "mds_stores": "Spotlight",
    "mdworker": "Spotlight",
    "mdworker_shared": "Spotlight",
    "fseventsd": "sistema de archivos de macOS",
    "bird": "iCloud",
    "cloudd": "iCloud",
}

#: Shells cuyo directorio actual puede estar dentro del punto de montaje. El
#: usuario no necesita cerrarlas — basta con salir del directorio (`cd ~`).
_SHELL_NAMES: frozenset[str] = frozenset({
    "zsh", "bash", "sh", "fish", "dash", "csh", "tcsh",
})

#: Mensaje de éxito en lenguaje de usuario — no el texto crudo de diskutil
#: (que casi siempre imprime algo tipo "Disk disk4 ejected").
_EJECT_SUCCESS_MSG = "iPod expulsado correctamente. Puedes desconectarlo."


@dataclass(frozen=True)
class Blocker:
    """Un proceso que impide la expulsión."""
    pid: int
    name: str                       # basename del binario
    path: Optional[str] = None      # ruta completa si el SO la reporta
    ppid: Optional[int] = None
    parent: Optional[str] = None
    source: str = ""                # "diskutil" | "lsof" | ...

    @property
    def friendly_name(self) -> str:
        return FRIENDLY_NAMES.get(self.name, self.name)


@dataclass(frozen=True)
class EjectResult:
    """Resultado de un intento de expulsión."""
    ejected: bool
    message: str
    blockers: tuple[Blocker, ...] = ()
    forced: bool = False
    platform: str = ""


# ──────────────────────────────────────────────────────────────────────
# Mensaje al usuario
# ──────────────────────────────────────────────────────────────────────
def _busy_message(blockers: list[Blocker]) -> str:
    if not blockers:
        return "El iPod está ocupado y no se pudo expulsar."

    shells = [b for b in blockers if b.name in _SHELL_NAMES]
    others = [b for b in blockers if b.name not in _SHELL_NAMES]

    parts: list[str] = []
    if others:
        nombres: list[str] = []
        for b in others:
            fn = b.friendly_name
            if fn not in nombres:
                nombres.append(fn)
        if len(nombres) == 1:
            parts.append(f"{nombres[0]} está usando el iPod, ciérralo e intenta de nuevo.")
        else:
            joined = ", ".join(nombres[:-1]) + f" y {nombres[-1]}"
            parts.append(f"{joined} están usando el iPod, ciérralos e intenta de nuevo.")
    if shells:
        parts.append(
            "Una terminal tiene su directorio actual dentro del iPod; "
            "sal de ahí con `cd ~` e intenta de nuevo."
        )
    return " ".join(parts)


# ──────────────────────────────────────────────────────────────────────
# Parser del disidente de diskutil (macOS)
# ──────────────────────────────────────────────────────────────────────
_DISSENT_RE = re.compile(r"dissented by PID\s+(\d+)\s+\(([^)]*)\)", re.IGNORECASE)
_PARENT_RE = re.compile(r"dissenter parent PPID\s+(\d+)\s+\(([^)]*)\)", re.IGNORECASE)


def _split_binary(raw: str) -> tuple[str, Optional[str]]:
    """(name, path) desde el paréntesis: ruta completa o solo nombre."""
    raw = raw.strip()
    if "/" in raw:
        return Path(raw).name, raw
    return raw, None


def _parse_diskutil_dissenters(text: str) -> list[Blocker]:
    """Extrae los bloqueadores del stderr de ``diskutil eject``/``unmount``."""
    parent_ppid: Optional[int] = None
    parent_path: Optional[str] = None
    pm = _PARENT_RE.search(text)
    if pm:
        parent_ppid = int(pm.group(1))
        parent_path = pm.group(2).strip() or None

    blockers: list[Blocker] = []
    for m in _DISSENT_RE.finditer(text):
        name, path = _split_binary(m.group(2))
        blockers.append(Blocker(
            pid=int(m.group(1)), name=name, path=path,
            ppid=parent_ppid, parent=parent_path, source="diskutil",
        ))
    return blockers


# ──────────────────────────────────────────────────────────────────────
# Fallback lsof (macOS y Linux): quién tiene abierto el punto de montaje
# ──────────────────────────────────────────────────────────────────────
def _lsof_blockers(mount: Path, *, timeout: float) -> list[Blocker]:
    if not shutil.which("lsof"):
        return []
    try:
        proc = subprocess.run(
            ["lsof", "-F", "pcn", "+D", str(mount)],
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    blockers: list[Blocker] = []
    pid: Optional[int] = None
    for line in proc.stdout.splitlines():
        if not line:
            continue
        tag, val = line[0], line[1:]
        if tag == "p":
            try:
                pid = int(val)
            except ValueError:
                pid = None
        elif tag == "c" and pid is not None:
            if not any(b.pid == pid for b in blockers):
                blockers.append(Blocker(pid=pid, name=val, source="lsof"))
    return blockers


# ──────────────────────────────────────────────────────────────────────
# macOS
# ──────────────────────────────────────────────────────────────────────
def _diskutil_info(mount: Path, *, timeout: float) -> dict:
    try:
        proc = subprocess.run(
            ["diskutil", "info", "-plist", str(mount)],
            capture_output=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {}
    if proc.returncode != 0 or not proc.stdout:
        return {}
    try:
        return plistlib.loads(proc.stdout)
    except Exception:
        return {}


def _eject_macos(mount: Path, *, force: bool, timeout: float) -> EjectResult:
    info = _diskutil_info(mount, timeout=timeout)
    # Seguridad: nunca expulsar un disco interno / no extraíble.
    if info and not (info.get("Ejectable") or info.get("RemovableMedia")):
        return EjectResult(False, "El volumen no es extraíble; no se expulsa.",
                           platform="darwin")
    disk = info.get("ParentWholeDisk") or info.get("DeviceIdentifier") or str(mount)

    try:
        proc = subprocess.run(["diskutil", "eject", disk],
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return EjectResult(False, "La expulsión excedió el tiempo límite.",
                           platform="darwin")
    except OSError as exc:
        return EjectResult(False, f"No se pudo ejecutar diskutil: {exc}",
                           platform="darwin")

    if proc.returncode == 0:
        logger.debug("diskutil eject stdout: %s", proc.stdout.strip())
        return EjectResult(True, _EJECT_SUCCESS_MSG, platform="darwin")

    text = (proc.stderr or "") + "\n" + (proc.stdout or "")
    blockers = _parse_diskutil_dissenters(text) or _lsof_blockers(mount, timeout=timeout)

    if force:
        return _force_eject_macos(mount, disk, blockers, timeout=timeout)
    return EjectResult(False, _busy_message(blockers), tuple(blockers), platform="darwin")


def _force_eject_macos(mount: Path, disk: str, blockers: list[Blocker], *,
                       timeout: float) -> EjectResult:
    """Vía forzada — SOLO cuando el usuario lo pide explícitamente."""
    try:
        subprocess.run(["diskutil", "unmountDisk", "force", disk],
                       capture_output=True, text=True, timeout=timeout)
        proc = subprocess.run(["diskutil", "eject", disk],
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return EjectResult(False, "La expulsión forzada excedió el tiempo límite.",
                           tuple(blockers), forced=True, platform="darwin")
    if proc.returncode == 0:
        return EjectResult(True, _EJECT_SUCCESS_MSG, tuple(blockers),
                           forced=True, platform="darwin")
    return EjectResult(False, "La expulsión forzada falló. " + _busy_message(blockers),
                       tuple(blockers), forced=True, platform="darwin")


# ──────────────────────────────────────────────────────────────────────
# Linux
# ──────────────────────────────────────────────────────────────────────
def _eject_linux(mount: Path, *, force: bool, timeout: float) -> EjectResult:
    cmd = ["umount"] + (["-l"] if force else []) + [str(mount)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return EjectResult(False, "La expulsión excedió el tiempo límite.",
                           forced=force, platform="linux")
    except OSError as exc:
        return EjectResult(False, f"No se pudo ejecutar umount: {exc}",
                           forced=force, platform="linux")
    if proc.returncode == 0:
        return EjectResult(True, "iPod desmontado." + (" (forzado)" if force else ""),
                           forced=force, platform="linux")
    blockers = _lsof_blockers(mount, timeout=timeout)
    return EjectResult(False, _busy_message(blockers), tuple(blockers),
                       forced=force, platform="linux")


# ──────────────────────────────────────────────────────────────────────
# Windows — ESBOZADO (ausencia declarada, no ctypes sin verificar)
# ──────────────────────────────────────────────────────────────────────
def _eject_windows_stub(mount: Path) -> EjectResult:
    return EjectResult(
        ejected=False,
        message=(
            "Expulsión en Windows aún no implementada; no se pueden identificar "
            "los procesos bloqueadores en Windows todavía. Expulsa el iPod desde "
            "el Explorador ('Quitar hardware de forma segura')."
        ),
        platform="win32",
    )


# ──────────────────────────────────────────────────────────────────────
# Entrada pública
# ──────────────────────────────────────────────────────────────────────
def eject_ipod(mount: str | Path, *, force: bool = False,
               timeout: float = 30.0) -> EjectResult:
    """Expulsa el iPod montado en ``mount``, identificando a quien bloquee.

    Hace flush antes (best-effort). ``force=False`` por defecto: la vía forzada
    solo se toma si el usuario lo pide explícitamente.
    """
    mount = Path(mount)
    ok, flush_msg = durability.flush_filesystem(mount, allow_unavailable=True)
    if not ok:
        logger.warning("Flush previo a la expulsión no confirmado: %s", flush_msg)

    plat = sys.platform
    if plat == "darwin":
        return _eject_macos(mount, force=force, timeout=timeout)
    if plat.startswith("linux"):
        return _eject_linux(mount, force=force, timeout=timeout)
    if plat.startswith("win"):
        return _eject_windows_stub(mount)
    return EjectResult(False, f"Expulsión no soportada en {plat}.", platform=plat)
