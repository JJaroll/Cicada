"""Codec RGB565_LE (Fase 4, Etapa 4b) — acotado a los 4 formatos del Nano 7G."""
import io

import pytest
from PIL import Image

from cicada.ipod.db.artwork.rgb565 import (
    convert_art_for_format,
    image_from_bytes,
    resize_for_format,
    rgb565_le_to_rgb888,
    rgb888_to_rgb565_le,
)
from cicada.ipod.device.artwork_presets import (
    ARTWORK_FORMATS_BY_ID,
    NANO_7G_COVER_ART_FORMATS,
    ArtworkFormat,
)

NANO_7G_BY_ID = {fmt.format_id: fmt for fmt in NANO_7G_COVER_ART_FORMATS}


def _jpeg_bytes(size=(300, 200), color=(255, 0, 0)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def _png_bytes(size=(50, 50), color=(0, 255, 0)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class TestImageFromBytes:
    def test_decodes_jpeg(self):
        img = image_from_bytes(_jpeg_bytes())
        assert img is not None
        assert img.mode == "RGB"

    def test_decodes_png_with_alpha(self):
        rgba = Image.new("RGBA", (10, 10), (10, 20, 30, 128))
        buf = io.BytesIO()
        rgba.save(buf, "PNG")
        img = image_from_bytes(buf.getvalue())
        assert img is not None
        assert img.mode == "RGB"

    def test_returns_none_for_garbage_bytes(self):
        assert image_from_bytes(b"not an image") is None

    def test_returns_none_for_empty_bytes(self):
        assert image_from_bytes(b"") is None


class TestResizeForFormat:
    @pytest.mark.parametrize("fmt", NANO_7G_COVER_ART_FORMATS)
    def test_resizes_to_exact_dimensions(self, fmt: ArtworkFormat):
        img = Image.new("RGB", (600, 400), (1, 2, 3))
        resized = resize_for_format(img, fmt)
        assert resized.size == (fmt.width, fmt.height)

    def test_upscales_small_source(self):
        fmt = ARTWORK_FORMATS_BY_ID[1010]  # 240x240
        img = Image.new("RGB", (16, 16), (1, 2, 3))
        resized = resize_for_format(img, fmt)
        assert resized.size == (240, 240)


class TestRgb888ToRgb565Le:
    def test_pure_red(self):
        img = Image.new("RGB", (1, 1), (255, 0, 0))
        data = rgb888_to_rgb565_le(img, 1, 1)
        # R=31 (0x1F) << 11, G=0, B=0
        assert data == (0x1F << 11).to_bytes(2, "little")

    def test_pure_green(self):
        img = Image.new("RGB", (1, 1), (0, 255, 0))
        data = rgb888_to_rgb565_le(img, 1, 1)
        # G=63 (0x3F) << 5
        assert data == (0x3F << 5).to_bytes(2, "little")

    def test_pure_blue(self):
        img = Image.new("RGB", (1, 1), (0, 0, 255))
        data = rgb888_to_rgb565_le(img, 1, 1)
        assert data == (0x1F).to_bytes(2, "little")

    def test_black(self):
        img = Image.new("RGB", (1, 1), (0, 0, 0))
        data = rgb888_to_rgb565_le(img, 1, 1)
        assert data == b"\x00\x00"

    def test_white(self):
        img = Image.new("RGB", (1, 1), (255, 255, 255))
        data = rgb888_to_rgb565_le(img, 1, 1)
        assert data == b"\xff\xff"

    def test_output_size_without_stride(self):
        img = Image.new("RGB", (4, 3), (10, 20, 30))
        data = rgb888_to_rgb565_le(img, 4, 3)
        assert len(data) == 4 * 3 * 2

    def test_stride_padding_adds_zero_pixels(self):
        img = Image.new("RGB", (2, 1), (255, 255, 255))
        data = rgb888_to_rgb565_le(img, 2, 1, stride=3)
        assert len(data) == 3 * 1 * 2
        assert data == b"\xff\xff\xff\xff\x00\x00"

    def test_mismatched_dimensions_raise(self):
        img = Image.new("RGB", (5, 5), (1, 2, 3))
        with pytest.raises(ValueError):
            rgb888_to_rgb565_le(img, 10, 10)


class TestConvertArtForFormat:
    @pytest.mark.parametrize("fmt", NANO_7G_COVER_ART_FORMATS)
    def test_produces_correct_size_for_every_nano7g_format(self, fmt: ArtworkFormat):
        payload = convert_art_for_format(_jpeg_bytes(), fmt)
        assert payload is not None
        assert payload.width == fmt.width
        assert payload.height == fmt.height
        assert payload.pixel_format == "RGB565_LE"
        expected_stride = fmt.row_bytes // 2
        assert payload.stride_pixels == expected_stride
        assert payload.size == len(payload.data)
        assert payload.size == expected_stride * fmt.height * 2

    def test_format_1016_has_alignment_padding(self):
        # 1016 (override Nano 7G): 57x57 visible, row_bytes=116 -> stride 58px -> hpad=1
        fmt = NANO_7G_BY_ID[1016]
        assert fmt.width == 57 and fmt.row_bytes == 116
        payload = convert_art_for_format(_jpeg_bytes(), fmt)
        assert payload.hpad == 1
        assert payload.stride_pixels == 58

    def test_formats_without_padding_have_zero_hpad(self):
        for fmt_id in (1010, 1013, 1015):
            fmt = NANO_7G_BY_ID[fmt_id]
            payload = convert_art_for_format(_jpeg_bytes(), fmt)
            assert payload.hpad == 0

    def test_accepts_png_source(self):
        fmt = NANO_7G_BY_ID[1013]
        payload = convert_art_for_format(_png_bytes(), fmt)
        assert payload is not None

    def test_returns_none_for_undecodable_bytes(self):
        fmt = ARTWORK_FORMATS_BY_ID[1010]
        assert convert_art_for_format(b"garbage", fmt) is None

    def test_rejects_non_rgb565_le_format(self):
        # 1019 = UYVY (TV-out) — fuera de alcance hasta la Etapa 4f.
        fmt = ARTWORK_FORMATS_BY_ID[1019]
        with pytest.raises(NotImplementedError):
            convert_art_for_format(_jpeg_bytes(), fmt)

    @pytest.mark.parametrize(
        "fmt_id", [2002, 3001, 1067, 1013]  # RGB565_BE, REC_RGB555_LE, I420_LE, RGB565_BE_90
    )
    def test_rejects_every_non_rgb565_le_global_format(self, fmt_id):
        fmt = ARTWORK_FORMATS_BY_ID[fmt_id]
        if fmt.pixel_format == "RGB565_LE":
            pytest.skip("format_id coincidentally RGB565_LE globally")
        with pytest.raises(NotImplementedError):
            convert_art_for_format(_jpeg_bytes(), fmt)


class TestRgb565LeToRgb888:
    """Decoder inverso — solo para verificación en staging (Etapa 4c)."""

    def test_decodes_pure_red(self):
        data = (0x1F << 11).to_bytes(2, "little")
        img = rgb565_le_to_rgb888(data, 1, 1)
        assert img.getpixel((0, 0)) == (255, 0, 0)

    def test_decodes_pure_green(self):
        data = (0x3F << 5).to_bytes(2, "little")
        img = rgb565_le_to_rgb888(data, 1, 1)
        assert img.getpixel((0, 0)) == (0, 255, 0)

    def test_decodes_pure_blue(self):
        data = (0x1F).to_bytes(2, "little")
        img = rgb565_le_to_rgb888(data, 1, 1)
        assert img.getpixel((0, 0)) == (0, 0, 255)

    def test_decodes_black_and_white(self):
        assert rgb565_le_to_rgb888(b"\x00\x00", 1, 1).getpixel((0, 0)) == (0, 0, 0)
        assert rgb565_le_to_rgb888(b"\xff\xff", 1, 1).getpixel((0, 0)) == (255, 255, 255)

    def test_ignores_stride_padding_columns(self):
        # 2px visibles + 1px de relleno a stride=3; el píxel de relleno
        # (blanco) no debe aparecer en la imagen decodificada de 2px.
        data = b"\xff\xff\xff\xff\x00\x00"  # blanco, blanco, negro(relleno)
        img = rgb565_le_to_rgb888(data, 2, 1, stride=3)
        assert img.size == (2, 1)
        assert img.getpixel((0, 0)) == (255, 255, 255)
        assert img.getpixel((1, 0)) == (255, 255, 255)

    @pytest.mark.parametrize("fmt", NANO_7G_COVER_ART_FORMATS)
    def test_round_trip_within_rgb565_quantization(self, fmt):
        # Colores puros solo pierden precisión de cuantización RGB565
        # (5/6/5 bits), no más: el decode debe reproducirlos exactos.
        img = Image.new("RGB", (fmt.width, fmt.height), (255, 128, 64))
        stride = fmt.row_bytes // 2
        encoded = rgb888_to_rgb565_le(img, fmt.width, fmt.height, stride=stride)
        decoded = rgb565_le_to_rgb888(encoded, fmt.width, fmt.height, stride=stride)
        r, g, b = decoded.getpixel((0, 0))
        assert abs(r - 255) <= 4
        assert abs(g - 128) <= 4
        assert abs(b - 64) <= 4
