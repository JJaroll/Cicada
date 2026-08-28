"""Tests para get_volume_label y volume_fingerprint en cicada/ipod/device/volume_id.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from cicada.ipod.device.volume_id import get_volume_label, volume_fingerprint


def test_get_volume_label_macos_volumes_path():
    mount = Path("/Volumes/IPOD JAROL")
    label = get_volume_label(mount)
    # En macOS debe extraer el nombre del volumen del directorio /Volumes/<Name>
    if sys.platform == "darwin":
        assert label == "IPOD JAROL"


def test_get_volume_label_none_or_empty():
    assert get_volume_label(None) is None
    assert get_volume_label("") is None


def test_get_volume_label_windows_mock():
    # Simula Windows con GetVolumeInformationW
    with patch("sys.platform", "win32"):
        with patch("ctypes.windll", create=True) as mock_windll:
            def fake_get_vol_info(drive, vol_buf, vol_buf_size, *args):
                vol_buf.value = "IPOD DE JAROL"
                return 1

            mock_windll.kernel32.GetVolumeInformationW = fake_get_vol_info
            res = get_volume_label("E:\\")
            assert res == "IPOD DE JAROL"
