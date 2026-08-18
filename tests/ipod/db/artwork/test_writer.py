"""Verificación de extremo a extremo del escritor de ArtworkDB (Etapa 4c).

No basta con que ArtworkDB/.ithmb reparseen sin excepción (eso ya lo cubre
test_chunks.py). Aquí se verifica, con imágenes de prueba conocidas
(patrones de 4 cuadrantes con colores distintos por track), que:

  1. El .ithmb generado, releído y decodificado reproduce los píxeles
     originales dentro del margen de pérdida de RGB565 (ya acotado en 4b).
  2. Los offsets que ArtworkDB registra en cada MHNI apuntan EXACTAMENTE
     a donde está cada imagen dentro del .ithmb — no solo que el archivo
     tenga el tamaño total esperado. Se comprueba decodificando el
     .ithmb en el offset leído del propio binario (no con contadores
     internos del test) y confirmando que NINGÚN track lee los píxeles
     de otro (contaminación cruzada de offsets sería el bug más probable).
  3. El song_id/img_id embebido en cada MHII corresponde al track correcto.

Todo en memoria/staging — no toca ningún dispositivo (eso es la Etapa 4d).
"""
import io

import pytest
from PIL import Image

from cicada.ipod.db.artwork.chunks import read_artworkdb
from cicada.ipod.db.artwork.rgb565 import rgb565_le_to_rgb888
from cicada.ipod.db.artwork.writer import (
    DEFAULT_START_IMG_ID,
    ArtworkSourceTrack,
    build_artwork_assets,
)
from cicada.ipod.device.artwork_presets import NANO_7G_COVER_ART_FORMATS

COLOR_TOLERANCE = 40  # JPEG + resize LANCZOS + cuantización RGB565 combinados

# Tres tracks con patrones de 4 cuadrantes totalmente distintos entre sí,
# para que cualquier mezcla de offsets entre tracks sea detectable.
TRACK_A = (111, ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)))       # rojo/verde/azul/amarillo
TRACK_B = (222, ((0, 255, 255), (255, 0, 255), (255, 255, 255), (0, 0, 0)))   # cian/magenta/blanco/negro
TRACK_C = (333, ((0, 128, 0), (128, 128, 128), (0, 0, 128), (128, 0, 0)))     # verde oscuro/gris/navy/granate


def _quadrant_jpeg(colors, size=(64, 64)) -> bytes:
    tl, tr, bl, br = colors
    w, h = size
    hw, hh = w // 2, h // 2
    img = Image.new("RGB", size)
    img.paste(Image.new("RGB", (hw, hh), tl), (0, 0))
    img.paste(Image.new("RGB", (w - hw, hh), tr), (hw, 0))
    img.paste(Image.new("RGB", (hw, h - hh), bl), (0, hh))
    img.paste(Image.new("RGB", (w - hw, h - hh), br), (hw, hh))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95)
    return buf.getvalue()


def _close(actual, expected, tol=COLOR_TOLERANCE) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual, expected))


def _sample_quadrants(img: Image.Image):
    w, h = img.size
    qw, qh = max(1, w // 4), max(1, h // 4)
    return {
        "tl": img.getpixel((qw, qh)),
        "tr": img.getpixel((w - qw - 1, qh)),
        "bl": img.getpixel((qw, h - qh - 1)),
        "br": img.getpixel((w - qw - 1, h - qh - 1)),
    }


@pytest.fixture(scope="module")
def build_result():
    tracks = [
        ArtworkSourceTrack(db_track_id=tid, art_bytes=_quadrant_jpeg(colors))
        for tid, colors in (TRACK_A, TRACK_B, TRACK_C)
    ]
    return tracks, build_artwork_assets(tracks)


@pytest.fixture(scope="module")
def parsed_by_track(build_result):
    _tracks, result = build_result
    entries = read_artworkdb(result.artworkdb)
    return {e.db_track_id: e for e in entries}


class TestTrackArtworkMapping:
    """Requisito 3: img_id/song_id corresponden al track correcto."""

    def test_all_tracks_got_an_entry(self, build_result):
        _tracks, result = build_result
        assert set(result.track_artwork.keys()) == {111, 222, 333}
        assert result.skipped_track_ids == ()

    def test_img_ids_sequential_in_track_order(self, build_result):
        _tracks, result = build_result
        assert result.track_artwork[111].img_id == DEFAULT_START_IMG_ID
        assert result.track_artwork[222].img_id == DEFAULT_START_IMG_ID + 1
        assert result.track_artwork[333].img_id == DEFAULT_START_IMG_ID + 2

    def test_parsed_artworkdb_has_one_mhii_per_track(self, parsed_by_track):
        assert set(parsed_by_track.keys()) == {111, 222, 333}

    def test_song_id_and_img_id_match_the_writer_result(self, build_result, parsed_by_track):
        _tracks, result = build_result
        for track_id, expected in result.track_artwork.items():
            entry = parsed_by_track[track_id]
            assert entry.db_track_id == track_id
            assert entry.img_id == expected.img_id
            assert entry.src_img_size == expected.src_img_size

    def test_src_img_size_matches_original_jpeg_length(self, build_result, parsed_by_track):
        tracks, _result = build_result
        for track in tracks:
            entry = parsed_by_track[track.db_track_id]
            assert entry.src_img_size == len(track.art_bytes)


class TestIthmbOffsetsAndPixels:
    """Requisitos 1 y 2: offsets exactos + round-trip de píxeles."""

    @pytest.mark.parametrize("fmt", NANO_7G_COVER_ART_FORMATS)
    def test_total_ithmb_size_is_exactly_three_frames(self, build_result, fmt):
        _tracks, result = build_result
        filename = f"F{fmt.format_id}_1.ithmb"
        frame_size = fmt.row_bytes * fmt.height
        assert len(result.ithmb_files[filename]) == 3 * frame_size

    @pytest.mark.parametrize("fmt", NANO_7G_COVER_ART_FORMATS)
    def test_offsets_are_exact_non_overlapping_cumulative_frames(self, build_result, parsed_by_track, fmt):
        _tracks, result = build_result
        frame_size = fmt.row_bytes * fmt.height
        expected_offsets = {111: 0, 222: frame_size, 333: 2 * frame_size}
        for track_id, expected_offset in expected_offsets.items():
            ref = parsed_by_track[track_id].formats[fmt.format_id]
            assert ref.ithmb_offset == expected_offset
            assert ref.size == frame_size

    @pytest.mark.parametrize(
        "fmt", NANO_7G_COVER_ART_FORMATS, ids=[f"fmt{f.format_id}" for f in NANO_7G_COVER_ART_FORMATS]
    )
    @pytest.mark.parametrize("track_id, colors", [TRACK_A, TRACK_B, TRACK_C], ids=["trackA", "trackB", "trackC"])
    def test_pixels_at_offset_from_artworkdb_match_original_track(
        self, build_result, parsed_by_track, fmt, track_id, colors
    ):
        """Decodifica usando el offset LEÍDO DEL PROPIO ArtworkDB (no un
        contador interno del test) y compara contra los 4 cuadrantes
        originales de ESE track — cualquier mezcla de offsets entre
        tracks haría fallar esto."""
        _tracks, result = build_result
        ref = parsed_by_track[track_id].formats[fmt.format_id]
        ithmb = result.ithmb_files[f"F{fmt.format_id}_1.ithmb"]

        raw = ithmb[ref.ithmb_offset: ref.ithmb_offset + ref.size]
        assert len(raw) == ref.size

        stride = ref.width + ref.hpad
        decoded = rgb565_le_to_rgb888(raw, ref.width, ref.height, stride=stride)
        sampled = _sample_quadrants(decoded)
        expected = {"tl": colors[0], "tr": colors[1], "bl": colors[2], "br": colors[3]}

        for corner, expected_color in expected.items():
            assert _close(sampled[corner], expected_color), (
                f"track={track_id} fmt={fmt.format_id} corner={corner}: "
                f"decoded={sampled[corner]} esperado~={expected_color}"
            )

    def test_no_cross_track_contamination_at_smallest_format(self, build_result, parsed_by_track):
        """Chequeo directo anti-mezcla: el cuadrante TL de cada track debe
        distinguirse del TL de los otros dos — si los offsets se solaparan
        o se calcularan mal, dos tracks decodificarían el mismo color."""
        _tracks, result = build_result
        fmt = NANO_7G_COVER_ART_FORMATS[0]
        ithmb = result.ithmb_files[f"F{fmt.format_id}_1.ithmb"]

        tl_by_track = {}
        for track_id, _colors in (TRACK_A, TRACK_B, TRACK_C):
            ref = parsed_by_track[track_id].formats[fmt.format_id]
            raw = ithmb[ref.ithmb_offset: ref.ithmb_offset + ref.size]
            stride = ref.width + ref.hpad
            decoded = rgb565_le_to_rgb888(raw, ref.width, ref.height, stride=stride)
            tl_by_track[track_id] = _sample_quadrants(decoded)["tl"]

        assert not _close(tl_by_track[111], tl_by_track[222], tol=60)
        assert not _close(tl_by_track[111], tl_by_track[333], tol=60)
        assert not _close(tl_by_track[222], tl_by_track[333], tol=60)


class TestUndecodableArtworkIsSkippedNotFatal:
    def test_bad_art_bytes_are_skipped_not_raised(self):
        tracks = [
            ArtworkSourceTrack(db_track_id=1, art_bytes=_quadrant_jpeg(TRACK_A[1])),
            ArtworkSourceTrack(db_track_id=2, art_bytes=b"not a real image"),
            ArtworkSourceTrack(db_track_id=3, art_bytes=_quadrant_jpeg(TRACK_B[1])),
        ]
        result = build_artwork_assets(tracks)
        assert result.skipped_track_ids == (2,)
        assert set(result.track_artwork.keys()) == {1, 3}

    def test_skipped_track_does_not_consume_an_img_id(self):
        tracks = [
            ArtworkSourceTrack(db_track_id=1, art_bytes=b"garbage"),
            ArtworkSourceTrack(db_track_id=2, art_bytes=_quadrant_jpeg(TRACK_A[1])),
        ]
        result = build_artwork_assets(tracks)
        assert result.track_artwork[2].img_id == DEFAULT_START_IMG_ID

    def test_all_undecodable_produces_valid_empty_artworkdb(self):
        tracks = [ArtworkSourceTrack(db_track_id=1, art_bytes=b"garbage")]
        result = build_artwork_assets(tracks)
        assert result.track_artwork == {}
        assert result.skipped_track_ids == (1,)
        entries = read_artworkdb(result.artworkdb)
        assert entries == []
