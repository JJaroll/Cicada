"""Tests de eject — parser del bloqueador + expulsión con subprocess mockeado.

Ningún dispositivo real: se mockea subprocess.run. El parser se valida contra la
salida REAL de diskutil que produce AMPDevicesAgent.
"""
import plistlib
import subprocess
from types import SimpleNamespace

import pytest

from cicada.ipod.device import eject as ej
from cicada.ipod.device.eject import (
    Blocker,
    EjectResult,
    _busy_message,
    _parse_diskutil_dissenters,
    eject_ipod,
)

# Salida real de diskutil en el Mac del usuario (AMPDevicesAgent bloqueando).
REAL_DISSENT = (
    "Unmount of disk4 failed: at least one volume could not be unmounted\n"
    "Unmount was dissented by PID 15486 (/System/Library/PrivateFrameworks/"
    "AMPDevices.framework/Versions/A/Support/AMPDevicesAgent)\n"
    "Dissenter parent PPID 1 (/sbin/launchd)\n"
)


# --------------------------------------------------------------------------- #
# Parser contra la salida real
# --------------------------------------------------------------------------- #
def test_parser_salida_real_amp():
    blockers = _parse_diskutil_dissenters(REAL_DISSENT)
    assert len(blockers) == 1
    b = blockers[0]
    assert b.pid == 15486
    assert b.name == "AMPDevicesAgent"
    assert b.path == ("/System/Library/PrivateFrameworks/AMPDevices.framework/"
                      "Versions/A/Support/AMPDevicesAgent")
    assert b.ppid == 1
    assert b.parent == "/sbin/launchd"
    assert b.source == "diskutil"
    assert b.friendly_name == "Música"


def test_parser_parentesis_solo_nombre():
    texto = "Unmount was dissented by PID 42 (Finder)\n"
    (b,) = _parse_diskutil_dissenters(texto)
    assert b.pid == 42 and b.name == "Finder" and b.path is None
    assert b.friendly_name == "Finder"


def test_parser_varios_disidentes():
    texto = (
        "Unmount was dissented by PID 100 (mds)\n"
        "Unmount was dissented by PID 200 (/usr/sbin/bird)\n"
    )
    blockers = _parse_diskutil_dissenters(texto)
    assert {b.pid for b in blockers} == {100, 200}
    assert {b.friendly_name for b in blockers} == {"Spotlight", "iCloud"}


def test_parser_sin_disidente():
    assert _parse_diskutil_dissenters("Unmount failed: Resource busy\n") == []


# --------------------------------------------------------------------------- #
# friendly_name y mensaje al usuario
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("binario,esperado", [
    ("AMPDevicesAgent", "Música"),
    ("AMPLibraryAgent", "Música"),
    ("Finder", "Finder"),
    ("mds_stores", "Spotlight"),
    ("fseventsd", "sistema de archivos de macOS"),
    ("cloudd", "iCloud"),
    ("algo_desconocido", "algo_desconocido"),   # sin coincidencia -> crudo
])
def test_friendly_name(binario, esperado):
    assert Blocker(pid=1, name=binario).friendly_name == esperado


def test_mensaje_usuario_singular():
    msg = _busy_message([Blocker(pid=15486, name="AMPDevicesAgent", source="diskutil")])
    assert msg == "Música está usando el iPod, ciérralo e intenta de nuevo."


def test_mensaje_usuario_plural():
    msg = _busy_message([
        Blocker(pid=1, name="AMPDevicesAgent"),
        Blocker(pid=2, name="mds"),
    ])
    assert msg == "Música y Spotlight están usando el iPod, ciérralos e intenta de nuevo."


def test_mensaje_usuario_deduplica():
    # Dos binarios que mapean a "Música" -> un solo nombre.
    msg = _busy_message([
        Blocker(pid=1, name="AMPDevicesAgent"),
        Blocker(pid=2, name="AMPLibraryAgent"),
    ])
    assert msg == "Música está usando el iPod, ciérralo e intenta de nuevo."


@pytest.mark.parametrize("shell", ["zsh", "bash", "sh", "fish", "dash", "csh", "tcsh"])
def test_mensaje_usuario_shell_solo(shell):
    # Una terminal bloqueando: no se le pide "cerrarla", se le pide salir del directorio.
    msg = _busy_message([Blocker(pid=1, name=shell)])
    assert msg == ("Una terminal tiene su directorio actual dentro del iPod; "
                   "sal de ahí con `cd ~` e intenta de nuevo.")


def test_mensaje_usuario_shell_y_app_mixto():
    # Bloqueador mixto: la app se pide cerrar, la terminal se pide abandonar.
    msg = _busy_message([
        Blocker(pid=1, name="AMPDevicesAgent"),
        Blocker(pid=2, name="zsh"),
    ])
    assert msg == (
        "Música está usando el iPod, ciérralo e intenta de nuevo. "
        "Una terminal tiene su directorio actual dentro del iPod; "
        "sal de ahí con `cd ~` e intenta de nuevo."
    )


def test_mensaje_usuario_varias_shells_no_repite():
    # Dos shells bloqueando -> una sola cláusula (no una por proceso).
    msg = _busy_message([
        Blocker(pid=1, name="zsh"),
        Blocker(pid=2, name="bash"),
    ])
    assert msg == ("Una terminal tiene su directorio actual dentro del iPod; "
                   "sal de ahí con `cd ~` e intenta de nuevo.")


# --------------------------------------------------------------------------- #
# eject_ipod (macOS) con subprocess mockeado
# --------------------------------------------------------------------------- #
def _fake_run_factory(responses):
    """responses: función(cmd) -> (returncode, stdout, stderr)."""
    def fake_run(cmd, *a, **kw):
        rc, out, err = responses(cmd)
        # diskutil info -plist devuelve bytes; el resto texto.
        return SimpleNamespace(returncode=rc, stdout=out, stderr=err)
    return fake_run


@pytest.fixture
def force_macos(monkeypatch):
    monkeypatch.setattr(ej.sys, "platform", "darwin")
    monkeypatch.setattr(ej.durability, "flush_filesystem", lambda *a, **k: (True, "flush ok"))
    monkeypatch.setattr(ej.shutil, "which", lambda name: "/usr/bin/" + name)


def test_eject_exito(force_macos, monkeypatch, tmp_path):
    info = plistlib.dumps({"Ejectable": True, "ParentWholeDisk": "disk4"})

    def responses(cmd):
        if cmd[:3] == ["diskutil", "info", "-plist"]:
            return 0, info, b""
        if cmd[:2] == ["diskutil", "eject"]:
            return 0, "Disk disk4 ejected", ""
        return 1, "", "unexpected"
    monkeypatch.setattr(ej.subprocess, "run", _fake_run_factory(responses))

    res = eject_ipod(tmp_path / "IPOD")
    assert res.ejected is True
    assert res.platform == "darwin"
    assert res.blockers == ()
    # Mensaje en lenguaje de usuario, NO el texto crudo de diskutil ("Disk disk4 ejected").
    assert res.message == "iPod expulsado correctamente. Puedes desconectarlo."


def test_eject_bloqueado_devuelve_quien(force_macos, monkeypatch, tmp_path):
    info = plistlib.dumps({"Ejectable": True, "ParentWholeDisk": "disk4"})

    def responses(cmd):
        if cmd[:3] == ["diskutil", "info", "-plist"]:
            return 0, info, b""
        if cmd[:2] == ["diskutil", "eject"]:
            return 1, "", REAL_DISSENT
        return 1, "", ""
    monkeypatch.setattr(ej.subprocess, "run", _fake_run_factory(responses))

    res = eject_ipod(tmp_path / "IPOD")            # force=False por defecto
    assert res.ejected is False
    assert res.forced is False
    assert len(res.blockers) == 1
    assert res.blockers[0].pid == 15486
    assert res.message == "Música está usando el iPod, ciérralo e intenta de nuevo."


def test_eject_no_extraible_rechazado(force_macos, monkeypatch, tmp_path):
    # Disco interno / no extraíble -> no se intenta expulsar.
    info = plistlib.dumps({"Ejectable": False, "RemovableMedia": False, "Internal": True})
    ejectados = []

    def responses(cmd):
        if cmd[:3] == ["diskutil", "info", "-plist"]:
            return 0, info, b""
        if cmd[:2] == ["diskutil", "eject"]:
            ejectados.append(cmd)                  # NO debería llegar aquí
            return 0, "ejected", ""
        return 1, "", ""
    monkeypatch.setattr(ej.subprocess, "run", _fake_run_factory(responses))

    res = eject_ipod(tmp_path / "IPOD")
    assert res.ejected is False
    assert "no es extraíble" in res.message
    assert ejectados == []                         # nunca intentó expulsar


def test_eject_timeout(force_macos, monkeypatch, tmp_path):
    info = plistlib.dumps({"Ejectable": True, "ParentWholeDisk": "disk4"})

    def fake_run(cmd, *a, **kw):
        if cmd[:3] == ["diskutil", "info", "-plist"]:
            return SimpleNamespace(returncode=0, stdout=info, stderr=b"")
        raise subprocess.TimeoutExpired(cmd, 30)
    monkeypatch.setattr(ej.subprocess, "run", fake_run)

    res = eject_ipod(tmp_path / "IPOD")
    assert res.ejected is False
    assert "tiempo límite" in res.message


def test_force_solo_con_flag(force_macos, monkeypatch, tmp_path):
    info = plistlib.dumps({"Ejectable": True, "ParentWholeDisk": "disk4"})
    llamadas = []

    def responses(cmd):
        llamadas.append(cmd)
        if cmd[:3] == ["diskutil", "info", "-plist"]:
            return 0, info, b""
        if cmd[:3] == ["diskutil", "unmountDisk", "force"]:
            return 0, "forced", ""
        if cmd[:2] == ["diskutil", "eject"]:
            # Falla sin force; con force (tras unmountDisk) tiene éxito.
            forzado = any(c[:3] == ["diskutil", "unmountDisk", "force"] for c in llamadas)
            return (0, "ejected", "") if forzado else (1, "", REAL_DISSENT)
        return 1, "", ""
    monkeypatch.setattr(ej.subprocess, "run", _fake_run_factory(responses))

    res = eject_ipod(tmp_path / "IPOD", force=True)
    assert res.ejected is True
    assert res.forced is True
    assert any(c[:3] == ["diskutil", "unmountDisk", "force"] for c in llamadas)
    # Mismo tono amigable que la vía normal (antes decía "iPod expulsado (forzado).").
    assert res.message == "iPod expulsado correctamente. Puedes desconectarlo."


# --------------------------------------------------------------------------- #
# Windows esbozado — ausencia honesta
# --------------------------------------------------------------------------- #
def test_windows_esbozado_honesto(monkeypatch, tmp_path):
    monkeypatch.setattr(ej.sys, "platform", "win32")
    monkeypatch.setattr(ej.durability, "flush_filesystem", lambda *a, **k: (True, "ok"))
    res = eject_ipod(tmp_path / "IPOD")
    assert res.ejected is False
    assert res.platform == "win32"
    assert "Windows" in res.message
    assert res.blockers == ()
