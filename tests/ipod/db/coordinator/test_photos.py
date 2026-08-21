"""Coordinador de sync de Fotos (Fase 6, Etapa 6h) — round-trip real contra
un árbol de iPod simulado, backup/rollback verificado releyendo lo
realmente instalado, no lo que el código dice haber hecho.
"""
from pathlib import Path

import pytest
from PIL import Image

from cicada.ipod.db.artwork.chunks import read_photo_db
from cicada.ipod.db.coordinator import photos as photos_mod
from cicada.ipod.db.coordinator.photos import (
    UnsafePhotoDeviceError,
    image_visual_hash,
    scan_pc_photos,
    sync_photos_to_ipod,
)
from cicada.ipod.db.shared.device_time import DeviceTimeContext
from cicada.ipod.device.backup import list_backups
from cicada.ipod.device.capabilities import capabilities_for_family_gen
from cicada.ipod.device.device_info import DeviceInfo
from cicada.ipod.device.photo_mapping import PHOTO_SYNC_SETTINGS_KEY, read_photo_mapping

GUID = "000A27002484DDFB"


@pytest.fixture(autouse=True)
def _cicada_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CICADA_HOME", str(tmp_path / "cicada_home"))


@pytest.fixture
def ipod(tmp_path) -> Path:
    mount = tmp_path / "IPOD"
    (mount / "iPod_Control" / "Device").mkdir(parents=True)
    (mount / "iPod_Control" / "iTunes").mkdir(parents=True)
    return mount


@pytest.fixture
def device_info(ipod) -> DeviceInfo:
    caps = capabilities_for_family_gen("iPod Nano", "7th Gen")
    return DeviceInfo(
        mount=str(ipod), firewire_guid=GUID, family="iPod Nano", generation="7th Gen",
        capabilities=caps, guid_provenance="disk",
    )


def _make_photo(path: Path, size=(400, 300), color=(200, 50, 50)) -> None:
    Image.new("RGB", size, color).save(path)


def _make_photo_with_exif_capture(path: Path, capture_iso: str, size=(400, 300), color=(200, 50, 50)) -> None:
    """Foto con EXIF DateTimeOriginal real (tag 36867, Exif SubIFD 0x8769)
    — ``_make_photo`` no trae EXIF en absoluto, no sirve para probar la
    discrepancia F (Etapa 6j, quinto intento)."""
    img = Image.new("RGB", size, color)
    exif = img.getexif()
    exif.get_ifd(0x8769)[36867] = capture_iso
    img.save(path, exif=exif)


# ── scan_pc_photos / image_visual_hash ───────────────────────────────────


class TestScanPcPhotos:
    def test_dedup_por_hash_visual_no_por_ruta(self, tmp_path):
        src = tmp_path / "lib"
        src.mkdir()
        _make_photo(src / "a.jpg", color=(10, 20, 30))
        _make_photo(src / "a_copia.jpg", color=(10, 20, 30))  # mismo color, otro nombre
        items = scan_pc_photos(src)
        assert len(items) == 1  # deduplicadas por contenido visual

    def test_fotos_distintas_no_se_deduplican(self, tmp_path):
        src = tmp_path / "lib"
        src.mkdir()
        _make_photo(src / "a.jpg", color=(10, 20, 30))
        _make_photo(src / "b.jpg", color=(200, 100, 50))
        items = scan_pc_photos(src)
        assert len(items) == 2

    def test_subdirectorio_se_convierte_en_album(self, tmp_path):
        src = tmp_path / "lib"
        (src / "Vacaciones").mkdir(parents=True)
        _make_photo(src / "raiz.jpg", color=(1, 1, 1))
        _make_photo(src / "Vacaciones" / "playa.jpg", color=(2, 2, 2))
        items = scan_pc_photos(src)
        by_name = {i.display_name: i for i in items}
        assert by_name["raiz.jpg"].album_names == frozenset()
        assert by_name["playa.jpg"].album_names == frozenset({"Vacaciones"})

    def test_extension_no_soportada_se_ignora(self, tmp_path):
        src = tmp_path / "lib"
        src.mkdir()
        (src / "nota.txt").write_text("no es una foto")
        assert scan_pc_photos(src) == []

    def test_directorio_inexistente_devuelve_vacio(self, tmp_path):
        assert scan_pc_photos(tmp_path / "no_existe") == []


def test_image_visual_hash_estable_para_el_mismo_contenido():
    img1 = Image.new("RGB", (400, 300), (10, 20, 30))
    img2 = Image.new("RGB", (400, 300), (10, 20, 30))
    assert image_visual_hash(img1) == image_visual_hash(img2)


def test_image_visual_hash_distinto_para_contenido_distinto():
    img1 = Image.new("RGB", (400, 300), (10, 20, 30))
    img2 = Image.new("RGB", (400, 300), (200, 100, 50))
    assert image_visual_hash(img1) != image_visual_hash(img2)


# ── sync_photos_to_ipod: precondiciones ──────────────────────────────────


def test_sync_rechaza_dispositivo_con_procedencia_insegura(ipod, tmp_path):
    caps = capabilities_for_family_gen("iPod Nano", "7th Gen")
    unsafe_dev = DeviceInfo(
        mount=str(ipod), firewire_guid=GUID, family="iPod Nano", generation="7th Gen",
        capabilities=caps, guid_provenance="cache_weak",  # no write-safe
    )
    src = tmp_path / "lib"
    src.mkdir()
    _make_photo(src / "a.jpg")
    with pytest.raises(UnsafePhotoDeviceError):
        sync_photos_to_ipod(ipod, src, device_info=unsafe_dev)


# ── sync_photos_to_ipod: round-trip real ─────────────────────────────────


class TestSyncRoundTrip:
    def test_primer_sync_escribe_todo_y_es_verificable_releyendo(self, ipod, device_info, tmp_path):
        src = tmp_path / "lib"
        (src / "Magallanes").mkdir(parents=True)
        _make_photo(src / "a.jpg", color=(200, 50, 50))
        _make_photo(src / "Magallanes" / "b.jpg", color=(50, 200, 50))

        result = sync_photos_to_ipod(ipod, src, device_info=device_info)
        assert result.success
        assert result.photos_written == 2
        assert result.photos_added == 2
        assert result.backup_path is not None and result.backup_path.is_file()

        # Releer lo REALMENTE instalado, no confiar en el resultado.
        db_bytes = (ipod / "Photos" / "Photo Database").read_bytes()
        images, albums = read_photo_db(db_bytes)
        assert len(images) == 2
        album_names = {a.name for a in albums}
        assert album_names == {"Photo Library", "Magallanes"}
        magallanes = next(a for a in albums if a.name == "Magallanes")
        assert len(magallanes.members) == 1

        # Archivos reales en disco, no solo referenciados en la DB.
        for img in images:
            full_res = ipod / "Photos" / img.full_res.storage_path
            assert full_res.is_file() and full_res.stat().st_size > 0
            for thumb in img.thumbs.values():
                thumb_path = ipod / "Photos" / thumb.storage_path
                assert thumb_path.is_file()

    def test_created_at_digitized_at_son_epoca_mac_1904_no_unix(self, ipod, device_info, tmp_path):
        """Auditoría de 2026-08-20: comparado contra un Photo Database
        REAL escrito por Música/iTunes, created_at/digitized_at son
        segundos-mac (1904, hora local del dispositivo) — no Unix. Un
        valor Unix crudo decodifica a un año absurdo (~2092); el mismo
        valor reinterpretado como época 1904 da una fecha real y
        coincide con la carpeta real donde Apple guarda el archivo
        (Full Resolution/<año>/<mes>/<día>/). Mismo bug que ya mordió 3
        veces con fechas del iTunesCDB (Cocoa/2001) — ahora con época
        1904, en el único subsistema de Fotos sin respaldo SQLite."""
        import os

        src = tmp_path / "lib"
        src.mkdir()
        photo_path = src / "a.jpg"
        _make_photo(photo_path)
        # mtime conocido y controlado: 2026-05-28 23:23:52 UTC (cerca de
        # la fecha real observada en el dispositivo durante la auditoría,
        # 2026-05-29 — el valor exacto no importa, solo que decodifique
        # a una fecha de calendario real y no a un año absurdo).
        known_unix_mtime = 1780010632
        os.utime(photo_path, (known_unix_mtime, known_unix_mtime))

        result = sync_photos_to_ipod(ipod, src, device_info=device_info)
        assert result.success

        images, _ = read_photo_db((ipod / "Photos" / "Photo Database").read_bytes())
        assert len(images) == 1
        entry = images[0]

        expected_mac_timestamp = DeviceTimeContext.utc().unix_to_mac(known_unix_mtime)
        assert entry.created_at == expected_mac_timestamp
        assert entry.digitized_at == expected_mac_timestamp

        # El valor NO debe ser el timestamp Unix crudo (el bug que se corrige).
        assert entry.created_at != known_unix_mtime

        # Verificación independiente: decodificar el valor instalado como
        # época 1904 debe dar una fecha real de calendario, no un año
        # absurdo (que es lo que pasaba interpretándolo como Unix).
        import datetime
        mac_epoch = datetime.datetime(1904, 1, 1, tzinfo=datetime.timezone.utc)
        decoded = mac_epoch + datetime.timedelta(seconds=entry.created_at)
        assert 2020 <= decoded.year <= 2030

    def test_full_res_width_height_son_las_dimensiones_reales(self, ipod, device_info, tmp_path):
        """Discrepancia C (Etapa 6j, quinto intento): un Photo Database
        real trae width/height del MHNI de full-res poblados (10612x8086
        en la muestra auditada); Cicada escribía 0/0."""
        src = tmp_path / "lib"
        src.mkdir()
        _make_photo(src / "a.jpg", size=(640, 480))

        result = sync_photos_to_ipod(ipod, src, device_info=device_info)
        assert result.success

        images, _ = read_photo_db((ipod / "Photos" / "Photo Database").read_bytes())
        assert images[0].full_res.width == 640
        assert images[0].full_res.height == 480

    def test_original_size_es_cero_no_el_tamano_del_archivo_fuente(self, ipod, device_info, tmp_path):
        """Discrepancia D (Etapa 6j, quinto intento): confirmado 0 en las
        61 entradas reales — Cicada escribía el tamaño del .jpg de origen
        en la PC (offset 48 del header MHII)."""
        src = tmp_path / "lib"
        src.mkdir()
        photo_path = src / "a.jpg"
        _make_photo(photo_path, size=(800, 600))
        assert photo_path.stat().st_size > 0  # el archivo fuente sí pesa algo

        result = sync_photos_to_ipod(ipod, src, device_info=device_info)
        assert result.success

        images, _ = read_photo_db((ipod / "Photos" / "Photo Database").read_bytes())
        assert images[0].original_size == 0

    def test_created_at_usa_exif_digitized_at_usa_mtime_cuando_difieren(self, ipod, device_info, tmp_path):
        """Discrepancia F (Etapa 6j, quinto intento): un Photo Database
        real trae created_at (fecha de captura) distinto de digitized_at
        (fecha de import) — Cicada igualaba ambos al mtime del archivo.
        Sin fecha de import real disponible, se aproxima con EXIF
        DateTimeOriginal para created_at y mtime para digitized_at (ver
        docstring de _exif_capture_timestamp)."""
        import os

        src = tmp_path / "lib"
        src.mkdir()
        photo_path = src / "a.jpg"
        _make_photo_with_exif_capture(photo_path, "2024:03:15 10:30:00")
        # mtime deliberadamente MUY distinto de la fecha EXIF de captura.
        mtime_unix = 1780010632  # 2026-05-28, muy lejos del 2024-03-15 EXIF
        os.utime(photo_path, (mtime_unix, mtime_unix))

        result = sync_photos_to_ipod(ipod, src, device_info=device_info)
        assert result.success

        images, _ = read_photo_db((ipod / "Photos" / "Photo Database").read_bytes())
        entry = images[0]
        assert entry.created_at != entry.digitized_at

        expected_digitized = DeviceTimeContext.utc().unix_to_mac(mtime_unix)
        assert entry.digitized_at == expected_digitized

        import datetime
        expected_capture_unix = int(datetime.datetime(2024, 3, 15, 10, 30, 0).timestamp())
        expected_created = DeviceTimeContext.utc().unix_to_mac(expected_capture_unix)
        assert entry.created_at == expected_created

    def test_sin_exif_created_at_y_digitized_at_siguen_iguales(self, ipod, device_info, tmp_path):
        """Fallback documentado: sin EXIF DateTimeOriginal (caso de
        _make_photo, igual que antes de esta etapa), ambas fechas siguen
        siendo el mismo mtime — no un cambio de comportamiento sorpresa
        para el caso ya cubierto por
        test_created_at_digitized_at_son_epoca_mac_1904_no_unix."""
        src = tmp_path / "lib"
        src.mkdir()
        _make_photo(src / "a.jpg")

        result = sync_photos_to_ipod(ipod, src, device_info=device_info)
        assert result.success

        images, _ = read_photo_db((ipod / "Photos" / "Photo Database").read_bytes())
        assert images[0].created_at == images[0].digitized_at

    def test_segundo_sync_sin_cambios_es_no_op(self, ipod, device_info, tmp_path):
        src = tmp_path / "lib"
        src.mkdir()
        _make_photo(src / "a.jpg")
        sync_photos_to_ipod(ipod, src, device_info=device_info)
        backups_before = len(list_backups(guid=GUID))

        result = sync_photos_to_ipod(ipod, src, device_info=device_info)
        assert result.success
        assert result.backup_path is None
        assert result.photos_added == 0 and result.photos_removed == 0
        assert len(list_backups(guid=GUID)) == backups_before  # no se creó backup nuevo

    def test_image_id_estable_entre_syncs_para_la_misma_foto(self, ipod, device_info, tmp_path):
        src = tmp_path / "lib"
        src.mkdir()
        _make_photo(src / "a.jpg", color=(1, 2, 3))
        sync_photos_to_ipod(ipod, src, device_info=device_info)
        images1, _ = read_photo_db((ipod / "Photos" / "Photo Database").read_bytes())
        id1 = images1[0].image_id

        _make_photo(src / "b.jpg", color=(9, 9, 9))  # agrega una segunda foto
        sync_photos_to_ipod(ipod, src, device_info=device_info)
        images2, _ = read_photo_db((ipod / "Photos" / "Photo Database").read_bytes())
        ids_by_hash = {img.image_id for img in images2}
        assert id1 in ids_by_hash  # la primera foto conserva su image_id

    def test_foto_removida_borra_su_full_res_y_actualiza_la_db(self, ipod, device_info, tmp_path):
        src = tmp_path / "lib"
        src.mkdir()
        _make_photo(src / "a.jpg", color=(1, 2, 3))
        _make_photo(src / "b.jpg", color=(9, 9, 9))
        sync_photos_to_ipod(ipod, src, device_info=device_info)
        images1, _ = read_photo_db((ipod / "Photos" / "Photo Database").read_bytes())
        full_res_paths = {img.image_id: ipod / "Photos" / img.full_res.storage_path for img in images1}

        (src / "a.jpg").unlink()
        result = sync_photos_to_ipod(ipod, src, device_info=device_info)
        assert result.photos_removed == 1
        images2, _ = read_photo_db((ipod / "Photos" / "Photo Database").read_bytes())
        assert len(images2) == 1

        removed_id = next(iid for iid in full_res_paths if iid not in {i.image_id for i in images2})
        assert not full_res_paths[removed_id].exists()

    def test_mapa_off_device_no_deja_nada_en_el_volumen(self, ipod, device_info, tmp_path):
        src = tmp_path / "lib"
        src.mkdir()
        _make_photo(src / "a.jpg")
        sync_photos_to_ipod(ipod, src, device_info=device_info)
        mapping = read_photo_mapping(GUID)
        photo_entries = {k: v for k, v in mapping.items() if k != PHOTO_SYNC_SETTINGS_KEY}
        assert len(photo_entries) == 1
        # Nada de esto se escribió en el propio volumen del iPod.
        assert not (ipod / "Photos" / "photo_sync.json").exists()
        assert not list((ipod / "Photos").rglob("*.json"))


# ── rollback ante fallo ────────────────────────────────────────────────────


class TestRollback:
    def test_fallo_en_verificacion_post_commit_dispara_rollback(self, ipod, device_info, tmp_path, monkeypatch):
        src = tmp_path / "lib"
        src.mkdir()
        _make_photo(src / "a.jpg", color=(1, 2, 3))
        sync_photos_to_ipod(ipod, src, device_info=device_info)  # estado inicial estable
        original_db_bytes = (ipod / "Photos" / "Photo Database").read_bytes()

        _make_photo(src / "b.jpg", color=(9, 9, 9))

        def _broken_read_photo_db(data):
            raise ValueError("verificación post-commit simulada rota")
        monkeypatch.setattr(photos_mod, "read_photo_db", _broken_read_photo_db)

        result = sync_photos_to_ipod(ipod, src, device_info=device_info)
        assert not result.success
        assert result.restored_from_backup
        # El dispositivo volvió EXACTAMENTE al estado previo al intento fallido.
        assert (ipod / "Photos" / "Photo Database").read_bytes() == original_db_bytes

    def test_rollback_no_deja_temporales_de_staging(self, ipod, device_info, tmp_path, monkeypatch):
        src = tmp_path / "lib"
        src.mkdir()
        _make_photo(src / "a.jpg")
        sync_photos_to_ipod(ipod, src, device_info=device_info)

        _make_photo(src / "b.jpg", color=(9, 9, 9))
        monkeypatch.setattr(
            photos_mod, "read_photo_db",
            lambda data: (_ for _ in ()).throw(ValueError("roto a propósito")),
        )
        sync_photos_to_ipod(ipod, src, device_info=device_info)

        leftovers = list((ipod / "Photos").rglob("*.cicada-new"))
        assert leftovers == []
