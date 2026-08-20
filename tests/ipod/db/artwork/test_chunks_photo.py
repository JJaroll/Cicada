"""Round-trip binario de los chunks nuevos de Fotos (Fase 6, Etapa 6f):
MHBA/MHIA y la variante de MHII/MHNI con semántica de Fotos.

Mismo rigor que 4c (tests/ipod/db/artwork/test_chunks.py): verificar
offsets exactos, no solo "decodifica lo que el propio escritor codificó" —
un mismo tamaño de header con semántica de campos incompatible (el caso
real entre write_mhii de cover art y write_mhii_photo) es exactamente el
tipo de error silencioso que un round-trip *interno* no atraparía si el
bug estuviera simétrico en escritura y lectura. Por eso varios tests de
aquí desempaquetan los bytes crudos con struct en vez de pasar solo por
las funciones de este módulo.
"""
import struct

from cicada.ipod.db.artwork.chunks import (
    MHBA_HEADER_SIZE,
    MHIA_HEADER_SIZE,
    MHII_HEADER_SIZE,
    MHNI_HEADER_SIZE,
    PHOTO_FULL_RESOLUTION_FORMAT_ID,
    build_photo_db,
    photo_db_string_to_rel_path,
    photo_rel_path_to_db_string,
    read_photo_db,
    write_mhba,
    write_mhia,
    write_mhii,
    write_mhii_photo,
    write_mhla,
    write_mhni_photo,
)
from cicada.ipod.db.artwork.types import EncodedFormatPayload, PhotoAlbumInput


def _payload(width=4, height=4, hpad=0, vpad=0, size=None) -> EncodedFormatPayload:
    stride = width + hpad
    n = size if size is not None else stride * height * 2
    data = bytes(range(256))[:n].ljust(n, b"\x00")
    return EncodedFormatPayload(
        data=data, width=width, height=height, size=len(data),
        stride_pixels=stride, hpad=hpad, vpad=vpad, pixel_format="RGB565_LE",
    )


# ── Rutas con convención HFS ────────────────────────────────────────────────

def test_photo_rel_path_to_db_string_un_segmento():
    assert photo_rel_path_to_db_string("Thumbs/F1005_1.ithmb") == ":Thumbs:F1005_1.ithmb"


def test_photo_rel_path_to_db_string_multi_segmento():
    assert (
        photo_rel_path_to_db_string("Full Resolution/iOpenPod/foto_00123.jpg")
        == ":Full Resolution:iOpenPod:foto_00123.jpg"
    )


def test_photo_db_string_to_rel_path_round_trip():
    original = "Full Resolution/iOpenPod/foto_00123.jpg"
    assert photo_db_string_to_rel_path(photo_rel_path_to_db_string(original)) == original


# ── MHIA / MHBA ──────────────────────────────────────────────────────────────

def test_mhia_layout_exacto():
    blob = write_mhia(image_id=12345)
    assert len(blob) == MHIA_HEADER_SIZE == 40
    assert blob[0:4] == b"mhia"
    assert struct.unpack_from("<I", blob, 4)[0] == MHIA_HEADER_SIZE  # header_len
    assert struct.unpack_from("<I", blob, 8)[0] == MHIA_HEADER_SIZE  # total_len
    assert struct.unpack_from("<I", blob, 16)[0] == 12345  # image_id


def test_mhba_layout_exacto_todos_los_campos():
    album = PhotoAlbumInput(
        album_id=777,
        name="Vacaciones",
        members=(100, 101, 102),
        album_type=6,  # Nano 6G/7G
        playmusic=1,
        repeat=1,
        random=0,
        show_titles=1,
        transition_direction=3,
        slide_duration=5000,
        transition_duration=750,
        song_id=0xFEEDFACE12345678,
        prev_album_id=100,
    )
    blob = write_mhba(album)
    assert blob[0:4] == b"mhba"
    header_len = struct.unpack_from("<I", blob, 4)[0]
    assert header_len == MHBA_HEADER_SIZE == 148
    assert struct.unpack_from("<I", blob, 12)[0] == 1  # constante fija
    assert struct.unpack_from("<I", blob, 16)[0] == 3  # len(members)
    assert struct.unpack_from("<I", blob, 20)[0] == 777  # album_id
    assert blob[30] == 6  # album_type
    assert blob[31] == 1  # playmusic
    assert blob[32] == 1  # repeat
    assert blob[33] == 0  # random
    assert blob[34] == 1  # show_titles
    assert blob[35] == 3  # transition_direction
    assert struct.unpack_from("<I", blob, 36)[0] == 5000  # slide_duration
    assert struct.unpack_from("<I", blob, 40)[0] == 750  # transition_duration
    assert struct.unpack_from("<Q", blob, 52)[0] == 0xFEEDFACE12345678  # song_id
    assert struct.unpack_from("<I", blob, 60)[0] == 100  # prev_album_id

    # El primer hijo es el MHOD del nombre; los 3 MHIA vienen después, en orden.
    mhod_offset = header_len
    assert blob[mhod_offset:mhod_offset + 4] == b"mhod"
    mhod_total = struct.unpack_from("<I", blob, mhod_offset + 8)[0]
    child_offset = mhod_offset + mhod_total
    for expected_id in (100, 101, 102):
        assert blob[child_offset:child_offset + 4] == b"mhia"
        assert struct.unpack_from("<I", blob, child_offset + 16)[0] == expected_id
        child_offset += MHIA_HEADER_SIZE


def test_mhba_album_vacio_sin_miembros():
    album = PhotoAlbumInput(album_id=1, name="Vacío", members=())
    blob = write_mhba(album)
    assert struct.unpack_from("<I", blob, 16)[0] == 0
    assert len(blob) > MHBA_HEADER_SIZE  # solo el MHOD del nombre, ningún mhia


# ── MHNI/MHII de Fotos: layout distinto a cover art, mismo tamaño de header ──

def test_mhii_photo_mismo_tamano_de_header_que_cover_art():
    """La afirmación central de la investigación de Fotos: comparten
    contenedor. Verificado con el propio tamaño de header, no solo
    documentado en prosa."""
    payload = _payload()
    blob_cover = write_mhii(
        img_id=1, db_track_id=1, src_img_size=1,
        formats={1010: payload}, offsets={1010: 0}, filenames={1010: "F1010_1.ithmb"},
    )
    blob_photo = write_mhii_photo(
        image_id=1, created_at=1, digitized_at=1, original_size=1,
        full_res_payload=_payload(size=10), full_res_storage_path="Full Resolution/iOpenPod/x.jpg",
        thumb_formats={1005: payload}, thumb_offsets={1005: 0},
        thumb_storage_paths={1005: "Thumbs/F1005_1.ithmb"},
    )
    assert struct.unpack_from("<I", blob_cover, 4)[0] == struct.unpack_from("<I", blob_photo, 4)[0] == MHII_HEADER_SIZE


def test_mhii_photo_offset_20_no_es_song_id_sino_image_id_mas_2():
    """Si write_mhii_photo reusara por error el layout de cover art, offset
    20 (u64) tendría basura interpretada como song_id. Confirmamos que el
    escritor de Fotos NO hereda esa semántica: offset 20 (u32) guarda
    ``image_id + 2`` — patrón empírico confirmado sin excepción en las 61
    entradas de un Photo Database real escrito por Música/iTunes (Etapa
    6j, 2026-08-20; ver docs/VENDORED.md Paquete 9) — y offset 24 en
    adelante (resto del u64 que ocuparía song_id en cover art) sigue en
    cero, confirmando que no es un campo de 8 bytes reinterpretado."""
    blob = write_mhii_photo(
        image_id=42, created_at=1700000000, digitized_at=1700000001, original_size=999999,
        full_res_payload=_payload(size=10), full_res_storage_path="Full Resolution/iOpenPod/x.jpg",
        thumb_formats={}, thumb_offsets={}, thumb_storage_paths={},
    )
    assert struct.unpack_from("<I", blob, 20)[0] == 44  # image_id + 2
    assert struct.unpack_from("<I", blob, 24)[0] == 0
    # Los demás campos reales de Fotos SÍ están en 40/44/48.
    assert struct.unpack_from("<I", blob, 40)[0] == 1700000000
    assert struct.unpack_from("<I", blob, 44)[0] == 1700000001
    assert struct.unpack_from("<I", blob, 48)[0] == 999999


def test_mhni_photo_ruta_multi_segmento_round_trip():
    payload = _payload(width=240, height=240, hpad=4)
    blob = write_mhni_photo(1005, 8192, payload, "Full Resolution/iOpenPod/vacaciones_00042.jpg")
    assert blob[0:4] == b"mhni"
    assert struct.unpack_from("<I", blob, 4)[0] == MHNI_HEADER_SIZE == 76
    assert struct.unpack_from("<I", blob, 16)[0] == 1005  # format_id
    assert struct.unpack_from("<I", blob, 20)[0] == 8192  # ithmb_offset
    assert struct.unpack_from("<I", blob, 24)[0] == payload.size


class TestMhiiPhotoRoundTrip:
    def test_full_res_y_thumbs_completos(self):
        full_res = _payload(size=245678)
        thumb_medium = _payload(width=88, height=88)
        thumb_small = _payload(width=58, height=58, hpad=2)

        image_blob = write_mhii_photo(
            image_id=150,
            created_at=1755000000,
            digitized_at=1755000000,
            original_size=1234567,
            full_res_payload=full_res,
            full_res_storage_path="Full Resolution/iOpenPod/magallanes_00150.jpg",
            thumb_formats={1085: thumb_medium, 1089: thumb_small},
            thumb_offsets={1085: 0, 1089: thumb_medium.size},
            thumb_storage_paths={1085: "Thumbs/F1085_1.ithmb", 1089: "Thumbs/F1089_1.ithmb"},
        )
        db = build_photo_db(
            [image_blob], mhba_blobs=[],
            format_ids=[1085, 1089],
            image_sizes={1085: thumb_medium.size, 1089: thumb_small.size},
            next_img_id=151,
        )
        images, albums = read_photo_db(db)

        assert albums == []
        assert len(images) == 1
        entry = images[0]
        assert entry.image_id == 150
        assert entry.created_at == 1755000000
        assert entry.digitized_at == 1755000000
        assert entry.original_size == 1234567
        assert entry.persistent_id == 152  # image_id + 2
        assert entry.has_mhaf_marker is True

        assert entry.full_res is not None
        assert entry.full_res.format_id == PHOTO_FULL_RESOLUTION_FORMAT_ID
        assert entry.full_res.size == full_res.size
        assert entry.full_res.storage_path == "Full Resolution/iOpenPod/magallanes_00150.jpg"

        assert set(entry.thumbs.keys()) == {1085, 1089}
        assert entry.thumbs[1085].ithmb_offset == 0
        assert entry.thumbs[1085].width == 88
        assert entry.thumbs[1089].ithmb_offset == thumb_medium.size
        assert entry.thumbs[1089].hpad == 2
        assert entry.thumbs[1089].storage_path == "Thumbs/F1089_1.ithmb"


class TestMhiiPhotoMhafMarker:
    """Etapa 6j (2026-08-20): el 4º hijo (MHOD tipo 6, "mhaf") y offset 20
    ("persistent_id" = image_id + 2) que un Photo Database real de
    Música/iTunes escribe en TODAS sus entradas y que Cicada nunca había
    modelado. Ver docs/VENDORED.md, Paquete 9."""

    def test_child_count_y_total_len_incluyen_el_mhaf(self):
        blob = write_mhii_photo(
            image_id=42, created_at=1700000000, digitized_at=1700000001, original_size=999999,
            full_res_payload=_payload(size=10), full_res_storage_path="Full Resolution/iOpenPod/x.jpg",
            thumb_formats={}, thumb_offsets={}, thumb_storage_paths={},
        )
        assert struct.unpack_from("<I", blob, 12)[0] == 2  # full-res + mhaf, sin thumbs

        pos = MHII_HEADER_SIZE
        mhod_total_0 = struct.unpack_from("<I", blob, pos + 8)[0]
        pos += mhod_total_0
        assert blob[pos:pos + 4] == b"mhod"
        mhod_type = struct.unpack_from("<H", blob, pos + 12)[0]
        assert mhod_type == 6
        mhod_header_len = struct.unpack_from("<I", blob, pos + 4)[0]
        mhod_total = struct.unpack_from("<I", blob, pos + 8)[0]
        assert mhod_total - mhod_header_len == 96

    def test_contenido_del_mhaf_es_byte_identico_al_extraido_del_real(self):
        from cicada.ipod.db.artwork.chunks import MHAF_STATIC_BLOB
        blob = write_mhii_photo(
            image_id=42, created_at=0, digitized_at=0, original_size=0,
            full_res_payload=_payload(size=10), full_res_storage_path="Full Resolution/iOpenPod/x.jpg",
            thumb_formats={}, thumb_offsets={}, thumb_storage_paths={},
        )
        assert blob[-96:] == MHAF_STATIC_BLOB
        assert MHAF_STATIC_BLOB[0:4] == b"mhaf"
        assert len(MHAF_STATIC_BLOB) == 96


class TestBuildPhotoDbFull:
    def test_imagenes_y_albumes_juntos(self):
        payload = _payload()
        image_blobs = [
            write_mhii_photo(
                image_id=100 + i, created_at=1700000000 + i, digitized_at=1700000000 + i,
                original_size=1000 + i,
                full_res_payload=_payload(size=10), full_res_storage_path=f"Full Resolution/iOpenPod/f{i}.jpg",
                thumb_formats={1005: payload}, thumb_offsets={1005: i * payload.size},
                thumb_storage_paths={1005: "Thumbs/F1005_1.ithmb"},
            )
            for i in range(3)
        ]
        album_master = PhotoAlbumInput(album_id=200, name="Photo Library", members=(100, 101, 102), album_type=1)
        album_user = PhotoAlbumInput(album_id=201, name="Magallanes 120", members=(100, 102), album_type=6)

        db = build_photo_db(
            image_blobs,
            mhba_blobs=[write_mhba(album_master), write_mhba(album_user)],
            format_ids=[1005], image_sizes={1005: payload.size}, next_img_id=202,
        )
        images, albums = read_photo_db(db)

        assert [img.image_id for img in images] == [100, 101, 102]
        assert len(albums) == 2
        assert albums[0].name == "Photo Library"
        assert albums[0].members == [100, 101, 102]
        assert albums[1].name == "Magallanes 120"
        assert albums[1].members == [100, 102]
        assert albums[1].album_type == 6

    def test_mhfd_unknown2_es_6_no_2(self):
        """Fotos usa unknown2=6 (empírico, distinto del 2 de cover art) —
        confirmado leyendo el byte crudo, no solo confiando en el default."""
        db = build_photo_db([], mhba_blobs=[], format_ids=[], image_sizes={}, next_img_id=100)
        assert struct.unpack_from("<I", db, 16)[0] == 6

    def test_mhfd_offset_48_sigue_en_cero_en_build_photo_db(self):
        """build_photo_db() hereda el offset 48 de write_mhfd() — que
        deliberadamente sigue en 0 (ver test_write_mhfd_offset_48_
        deliberadamente_en_cero en test_chunks.py) hasta entender qué
        representa realmente ese campo contra un Photo Database real."""
        db = build_photo_db([], mhba_blobs=[], format_ids=[], image_sizes={}, next_img_id=100)
        assert struct.unpack_from("<I", db, 48)[0] == 0


# ── Regresión: cover art no debe cambiar de comportamiento ──────────────────

def test_write_mhla_sin_argumentos_sigue_vacia():
    """write_mhla() sin argumentos (como la llama build_artworkdb desde 4c)
    debe seguir produciendo 0 álbumes, byte a byte igual que antes de 6f."""
    blob = write_mhla()
    assert struct.unpack_from("<I", blob, 8)[0] == 0
    assert len(blob) == 92  # MHLA_HEADER_SIZE, sin datos de hijos


def test_write_mhii_cover_art_sin_cambios():
    """El write_mhii de cover art (4c) no se tocó — offset 20 sigue siendo
    song_id/db_track_id, no los campos de Fotos."""
    payload = _payload()
    blob = write_mhii(
        img_id=1, db_track_id=0xABCDEF, src_img_size=1,
        formats={1010: payload}, offsets={1010: 0}, filenames={1010: "F1010_1.ithmb"},
    )
    assert struct.unpack_from("<Q", blob, 20)[0] == 0xABCDEF
