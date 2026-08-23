"""Tests de safe_write — escrituras confinadas a iPod_Control vía write_guard.

Con tmp_path simulando el árbol del iPod. Cubre: escritura legítima dentro,
rechazo fuera, y rechazo vía symlink que apunta fuera.
"""
import sys

import pytest

from cicada.ipod.device.safe_write import (
    guarded_durable_replace,
    guarded_durable_unlink,
)
from cicada.ipod.device.write_guard import PathOutsideIpodControlError


@pytest.fixture
def ipod(tmp_path):
    mount = tmp_path / "IPOD"
    (mount / "iPod_Control" / "iTunes").mkdir(parents=True)
    return mount


def test_replace_dentro_de_control(ipod):
    itunes = ipod / "iPod_Control" / "iTunes"
    source = itunes / ".nuevo.tmp"
    source.write_bytes(b"datos-nuevos")
    target = itunes / "iTunesCDB"
    target.write_bytes(b"viejo")

    guarded_durable_replace(source, target, ipod)

    assert target.read_bytes() == b"datos-nuevos"
    assert not source.exists()


def test_unlink_dentro_de_control(ipod):
    victima = ipod / "iPod_Control" / "iTunes" / "borrame"
    victima.write_bytes(b"x")
    guarded_durable_unlink(victima, ipod)
    assert not victima.exists()


def test_replace_fuera_de_control_rechazado(ipod, tmp_path):
    source = ipod / "iPod_Control" / "iTunes" / ".nuevo.tmp"
    source.write_bytes(b"datos")
    fuera = tmp_path / "fuera" / "archivo"
    fuera.parent.mkdir()

    with pytest.raises(PathOutsideIpodControlError):
        guarded_durable_replace(source, fuera, ipod)

    assert not fuera.exists()
    assert source.exists()


def test_unlink_fuera_de_control_rechazado(ipod, tmp_path):
    fuera = tmp_path / "fuera.txt"
    fuera.write_bytes(b"no-tocar")
    with pytest.raises(PathOutsideIpodControlError):
        guarded_durable_unlink(fuera, ipod)
    assert fuera.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks POSIX")
def test_replace_via_symlink_que_apunta_fuera_rechazado(ipod, tmp_path):
    secreto = tmp_path / "secreto"
    secreto.mkdir()
    enlace = ipod / "iPod_Control" / "escape"
    enlace.symlink_to(secreto)

    source = ipod / "iPod_Control" / "iTunes" / ".nuevo.tmp"
    source.write_bytes(b"datos")
    target = enlace / "robado"

    with pytest.raises(PathOutsideIpodControlError):
        guarded_durable_replace(source, target, ipod)

    assert not (secreto / "robado").exists()
    assert source.exists()
