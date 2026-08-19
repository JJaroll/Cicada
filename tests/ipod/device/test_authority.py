"""Tests de authority (reimplementación propia off-device, Etapa 2b).

Todo con tmp_path: un árbol de iPod simulado + ~/.cicada redirigido por
CICADA_HOME. Sin dispositivo real. Se verifica: indexado por GUID (no por
montaje), carpeta ofuscada con sha256(guid)[:16], cero escrituras al volumen,
round-trip de procedencia con SOURCE_RANK, detección de manipulación, que el
iOpenPodSysInfoAuthority ajeno se ignore, y clean_foreign_authority.
"""
import hashlib
import json
import plistlib
from pathlib import Path

import pytest

from cicada.ipod.device import authority as auth
from cicada.ipod.device.authority import (
    FOREIGN_AUTHORITY_FILENAME,
    FOREIGN_BACKUP_RELPATHS,
    SOURCE_RANK,
    cache_sysinfo_extended,
    check_authority_coverage,
    clean_foreign_authority,
    read_authority,
    update_sysinfo,
)

GUID = "000A27002484DDFB"


def _make_ipod(root: Path, *, guid: str = GUID, sysinfo: bool = True,
               foreign: bool = False, foreign_backups: bool = False) -> Path:
    """Árbol mínimo de iPod con Device/SysInfoExtended (plist con FireWireGUID)."""
    mount = root / "IPOD"
    device = mount / "iPod_Control" / "Device"
    device.mkdir(parents=True)
    itlp = mount / "iPod_Control" / "iTunes" / "iTunes Library.itlp"
    itlp.mkdir(parents=True)
    (device / "SysInfoExtended").write_bytes(
        plistlib.dumps({"FireWireGUID": guid, "FamilyID": 18, "MaxTracks": 65534})
    )
    if sysinfo:
        (device / "SysInfo").write_text(
            f"FirewireGuid: 0x{guid}\nModelNumStr: \npszSerialNumber: ABC123\n"
        )
    if foreign:
        (device / FOREIGN_AUTHORITY_FILENAME).write_text('{"iopenpod": "data"}')
    if foreign_backups:
        for rel in FOREIGN_BACKUP_RELPATHS:
            p = mount / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("backup ajeno")
    return mount


@pytest.fixture(autouse=True)
def _cicada_home(tmp_path, monkeypatch):
    """Redirige ~/.cicada a un tmp para no tocar el real."""
    home = tmp_path / "cicada_home"
    monkeypatch.setenv("CICADA_HOME", str(home))
    return home


class _FakeDeviceInfo:
    """Duck-typing de DeviceInfo (info.py llega después)."""
    def __init__(self, path, guid=GUID, **fields):
        self.path = str(path)
        self.firewire_guid = guid
        self.model_number = fields.get("model_number", "MD480")
        self.serial = fields.get("serial", "ABC123")
        self._field_sources = fields.get("_field_sources", {})
        for k, v in fields.items():
            if k not in ("_field_sources",):
                setattr(self, k, v)


# --------------------------------------------------------------------------- #
# Indexado por GUID (no por montaje) + carpeta ofuscada
# --------------------------------------------------------------------------- #
def test_indexado_por_guid_no_por_montaje(tmp_path, _cicada_home):
    # El MISMO iPod (mismo GUID) en dos rutas distintas -> mismo caché.
    a = _make_ipod(tmp_path / "monte_a", guid=GUID)
    b = _make_ipod(tmp_path / "monte_b", guid=GUID)
    info = _FakeDeviceInfo(a, guid=GUID, _field_sources={"firewire_guid": "vpd"})
    update_sysinfo(info)

    # Leído desde la OTRA ruta de montaje: encuentra la misma autoridad.
    data = read_authority(str(b))
    assert data.get("firewire_guid") == GUID
    assert "FirewireGuid" in data["fields"]


def test_dispositivos_distintos_carpetas_separadas(tmp_path, _cicada_home):
    a = _make_ipod(tmp_path / "a", guid="AAAA0000AAAA0000")
    b = _make_ipod(tmp_path / "b", guid="BBBB1111BBBB1111")
    update_sysinfo(_FakeDeviceInfo(a, guid="AAAA0000AAAA0000",
                                   _field_sources={"firewire_guid": "vpd"}))
    update_sysinfo(_FakeDeviceInfo(b, guid="BBBB1111BBBB1111",
                                   _field_sources={"firewire_guid": "vpd"}))
    subdirs = sorted(p.name for p in (_cicada_home / "sysinfo").iterdir())
    assert len(subdirs) == 2


def test_carpeta_es_hash_no_guid_en_claro(tmp_path, _cicada_home):
    update_sysinfo(_FakeDeviceInfo(_make_ipod(tmp_path), guid=GUID,
                                   _field_sources={"firewire_guid": "vpd"}))
    esperado = hashlib.sha256(GUID.encode()).hexdigest()[:16]
    dirs = [p.name for p in (_cicada_home / "sysinfo").iterdir()]
    assert dirs == [esperado]
    assert GUID not in dirs[0]          # el GUID no aparece en la ruta
    # ...pero sí dentro del JSON.
    saved = json.loads((_cicada_home / "sysinfo" / esperado / "authority.json").read_text())
    assert saved["firewire_guid"] == GUID


# --------------------------------------------------------------------------- #
# Cero escrituras al volumen
# --------------------------------------------------------------------------- #
def test_no_escribe_en_el_volumen(tmp_path, _cicada_home):
    mount = _make_ipod(tmp_path)
    device = mount / "iPod_Control" / "Device"
    antes = {p.name for p in device.iterdir()}
    update_sysinfo(_FakeDeviceInfo(mount, _field_sources={"firewire_guid": "vpd"}))
    cache_sysinfo_extended(str(mount), b"<?xml version='1.0'?><plist><dict></dict></plist>", source="scsi_vpd")
    despues = {p.name for p in device.iterdir()}
    assert antes == despues            # nada nuevo en el dispositivo
    assert not (device / "authority.json").exists()


# --------------------------------------------------------------------------- #
# Round-trip de procedencia + SOURCE_RANK
# --------------------------------------------------------------------------- #
def test_source_rank_conserva_la_fuente_mas_fiable(tmp_path, _cicada_home):
    mount = _make_ipod(tmp_path)
    # Primera pasada: firewire_guid desde 'sysinfo' (poco fiable).
    update_sysinfo(_FakeDeviceInfo(mount, _field_sources={"firewire_guid": "sysinfo"}))
    assert read_authority(str(mount))["fields"]["FirewireGuid"]["source"] == "sysinfo"
    # Segunda pasada: desde 'vpd' (más fiable) -> debe upgradear.
    update_sysinfo(_FakeDeviceInfo(mount, _field_sources={"firewire_guid": "vpd"}))
    assert read_authority(str(mount))["fields"]["FirewireGuid"]["source"] == "vpd"
    # Tercera: 'sysinfo' de nuevo (peor) -> NO degrada.
    update_sysinfo(_FakeDeviceInfo(mount, _field_sources={"firewire_guid": "sysinfo"}))
    assert read_authority(str(mount))["fields"]["FirewireGuid"]["source"] == "vpd"
    assert SOURCE_RANK["vpd"] < SOURCE_RANK["sysinfo"]


def test_coverage_tras_update(tmp_path, _cicada_home):
    mount = _make_ipod(tmp_path)
    # SysInfo del fixture tiene FirewireGuid y pszSerialNumber; damos también model.
    info = _FakeDeviceInfo(mount, model_number="MD480",
                           firewire_guid=GUID, serial="ABC123",
                           _field_sources={"firewire_guid": "vpd", "serial": "vpd",
                                           "model_number": "itunes"})
    # Alinea el SysInfo del dispositivo con los valores para que coverage case.
    device = mount / "iPod_Control" / "Device"
    device.joinpath("SysInfo").write_text(
        f"FirewireGuid: 0x{GUID}\nModelNumStr: MD480\npszSerialNumber: ABC123\n"
    )
    update_sysinfo(info)
    all_tracked, sources = check_authority_coverage(str(mount))
    assert all_tracked is True
    assert sources["firewire_guid"] == "vpd"


# --------------------------------------------------------------------------- #
# Detección de manipulación externa
# --------------------------------------------------------------------------- #
def test_manipulacion_externa_invalida_coverage(tmp_path, _cicada_home):
    mount = _make_ipod(tmp_path)
    device = mount / "iPod_Control" / "Device"
    device.joinpath("SysInfo").write_text(
        f"FirewireGuid: 0x{GUID}\nModelNumStr: MD480\npszSerialNumber: ABC123\n"
    )
    update_sysinfo(_FakeDeviceInfo(mount, model_number="MD480",
                                   _field_sources={"firewire_guid": "vpd", "serial": "vpd",
                                                   "model_number": "itunes"}))
    assert check_authority_coverage(str(mount))[0] is True
    # iTunes reescribe el SysInfo del dispositivo -> hash cambia.
    device.joinpath("SysInfo").write_text("FirewireGuid: 0xDEADBEEFDEADBEEF\n")
    assert check_authority_coverage(str(mount))[0] is False


# --------------------------------------------------------------------------- #
# El iOpenPodSysInfoAuthority ajeno se ignora
# --------------------------------------------------------------------------- #
def test_read_authority_ignora_el_ajeno(tmp_path, _cicada_home):
    # Dispositivo con iOpenPodSysInfoAuthority presente pero SIN caché nuestro.
    mount = _make_ipod(tmp_path, foreign=True)
    assert (mount / "iPod_Control" / "Device" / FOREIGN_AUTHORITY_FILENAME).exists()
    # read_authority devuelve {} sin intentar parsear el archivo ajeno.
    assert read_authority(str(mount)) == {}


# --------------------------------------------------------------------------- #
# clean_foreign_authority
# --------------------------------------------------------------------------- #
def test_clean_foreign_elimina_el_ajeno(tmp_path, _cicada_home):
    mount = _make_ipod(tmp_path, foreign=True)
    foreign = mount / "iPod_Control" / "Device" / FOREIGN_AUTHORITY_FILENAME
    assert foreign.exists()
    removed = clean_foreign_authority(str(mount))
    assert removed == [f"iPod_Control/Device/{FOREIGN_AUTHORITY_FILENAME}"]
    assert not foreign.exists()
    # El resto de Device/ intacto.
    assert (mount / "iPod_Control" / "Device" / "SysInfoExtended").exists()


def test_clean_foreign_sin_archivo_devuelve_lista_vacia(tmp_path, _cicada_home):
    mount = _make_ipod(tmp_path, foreign=False)
    assert clean_foreign_authority(str(mount)) == []


def test_clean_foreign_mount_desaparecido(tmp_path, _cicada_home):
    import shutil
    from cicada.ipod.device.write_guard import MountNotFoundError
    mount = _make_ipod(tmp_path, foreign=True)
    shutil.rmtree(mount)
    with pytest.raises(MountNotFoundError):
        clean_foreign_authority(str(mount))


def test_clean_foreign_elimina_los_backup_ajenos(tmp_path, _cicada_home):
    """Los .backup en sitio de write_itunesdb/write_sqlite_databases de
    iOpenPod (Locations.itdb.backup, etc.) también se limpian."""
    mount = _make_ipod(tmp_path, foreign=False, foreign_backups=True)
    for rel in FOREIGN_BACKUP_RELPATHS:
        assert (mount / rel).exists()

    removed = clean_foreign_authority(str(mount))

    assert set(removed) == set(FOREIGN_BACKUP_RELPATHS)
    for rel in FOREIGN_BACKUP_RELPATHS:
        assert not (mount / rel).exists()


def test_clean_foreign_elimina_autoridad_y_backups_juntos(tmp_path, _cicada_home):
    """Escenario real (verificado en hardware): ambas categorías presentes
    a la vez, ambas se limpian, y la lista devuelta las nombra todas."""
    mount = _make_ipod(tmp_path, foreign=True, foreign_backups=True)

    removed = clean_foreign_authority(str(mount))

    expected = {f"iPod_Control/Device/{FOREIGN_AUTHORITY_FILENAME}", *FOREIGN_BACKUP_RELPATHS}
    assert set(removed) == expected
    assert not (mount / "iPod_Control" / "Device" / FOREIGN_AUTHORITY_FILENAME).exists()
    for rel in FOREIGN_BACKUP_RELPATHS:
        assert not (mount / rel).exists()
    # Archivos legítimos (no ajenos) intactos.
    assert (mount / "iPod_Control" / "Device" / "SysInfoExtended").exists()


def test_clean_foreign_no_toca_archivos_legitimos_homonimos_fuera_de_ruta(tmp_path, _cicada_home):
    """assert_within_ipod_control confina cada borrado a su ruta exacta — un
    archivo con nombre parecido en otro lugar del árbol no se toca."""
    mount = _make_ipod(tmp_path, foreign=False, foreign_backups=False)
    decoy = mount / "iPod_Control" / "iTunes" / "Library.itdb.backup.txt"
    decoy.write_text("no es el archivo ajeno real")

    removed = clean_foreign_authority(str(mount))

    assert removed == []
    assert decoy.exists()


# --------------------------------------------------------------------------- #
# GUID irresoluble -> degradación limpia
# --------------------------------------------------------------------------- #
def test_guid_irresoluble_degrada(tmp_path, _cicada_home):
    mount = tmp_path / "IPOD"
    (mount / "iPod_Control" / "Device").mkdir(parents=True)  # sin SysInfoExtended ni SysInfo
    assert read_authority(str(mount)) == {}
    assert check_authority_coverage(str(mount)) == (False, {})
    # update_sysinfo no explota aunque no haya GUID.
    update_sysinfo(_FakeDeviceInfo(mount, guid=""))
