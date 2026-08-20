"""Tests de storage_safety (Etapa 6e — infra para Fotos, vendorizado de iOpenPod).

Sin dispositivo real para el caso general: se mockea filesystem_type() igual
que el resto de los tests que dependen de diskutil (test_vpd_2d.py). El
round-trip contra hardware real vive en test_vpd_2d.py junto a filesystem_type,
que es la pieza que sí toca diskutil.
"""
import pytest

from cicada.ipod.device import storage_safety as mod
from cicada.ipod.device.storage_safety import (
    FileSizeLimitError,
    max_file_size_bytes_for_mount,
    require_file_size_supported,
)
from cicada.ipod.device.write_guard import WriteGuardError


def test_max_file_size_fat32(monkeypatch):
    monkeypatch.setattr(mod, "filesystem_type", lambda m: "msdos")
    assert max_file_size_bytes_for_mount("/Volumes/IPOD") == 4 * 1024**3 - 1


def test_max_file_size_desconocido_es_none(monkeypatch):
    monkeypatch.setattr(mod, "filesystem_type", lambda m: "exfat")
    assert max_file_size_bytes_for_mount("/Volumes/IPOD") is None


def test_max_file_size_sin_deteccion_es_none(monkeypatch):
    monkeypatch.setattr(mod, "filesystem_type", lambda m: None)
    assert max_file_size_bytes_for_mount("/Volumes/IPOD") is None


def test_require_file_size_supported_no_lanza_si_cabe():
    require_file_size_supported(1000, max_file_size_bytes=2000, display_name="F1005_1.ithmb")


def test_require_file_size_supported_lanza_si_excede():
    with pytest.raises(FileSizeLimitError):
        require_file_size_supported(5_000_000_000, max_file_size_bytes=4 * 1024**3 - 1, display_name="F1005_1.ithmb")


def test_require_file_size_supported_sin_limite_no_lanza():
    require_file_size_supported(999_999_999_999, max_file_size_bytes=None, display_name="F1005_1.ithmb")


def test_file_size_limit_error_es_write_guard_error():
    assert issubclass(FileSizeLimitError, WriteGuardError)


def test_mensaje_de_error_incluye_nombre_y_tamanos():
    with pytest.raises(FileSizeLimitError) as excinfo:
        require_file_size_supported(4_500_000_000, max_file_size_bytes=4 * 1024**3 - 1, display_name="F1005_1.ithmb")
    msg = str(excinfo.value)
    assert "F1005_1.ithmb" in msg
    assert "GB" in msg


# --------------------------------------------------------------------------- #
# Sanity check de mutación
# --------------------------------------------------------------------------- #
def test_mutacion_limite_invertido_no_detecta_el_exceso():
    """Si se invirtiera la comparación (lanzar cuando size <= limit en vez de
    size > limit), este test lo detectaría: un archivo que cabe justo no
    debería lanzar."""
    # size == limit exacto: no debe lanzar (frontera correcta es > , no >=)
    require_file_size_supported(2000, max_file_size_bytes=2000, display_name="x")
    with pytest.raises(FileSizeLimitError):
        require_file_size_supported(2001, max_file_size_bytes=2000, display_name="x")
