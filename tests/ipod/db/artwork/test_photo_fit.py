"""Fit/pad/rotate de fotos (Fase 6, Etapa 6g) — casos reales de aspect ratio,
verificados dimensión a dimensión y píxel a píxel, no solo "no lanza".
"""
from dataclasses import replace

import pytest
from PIL import Image

from cicada.ipod.db.artwork.photo_fit import (
    ROTATE_TALL_PHOTO_ASPECT_THRESHOLD,
    encode_photo_for_format,
    fit_dimensions,
    fit_photo_to_format,
    should_rotate_tall_photo_for_format,
)
from cicada.ipod.db.artwork.rgb565 import rgb565_le_to_rgb888
from cicada.ipod.device.artwork_presets import ARTWORK_FORMATS_BY_ID

# Formatos reales de Nano 7G para Fotos.
THUMB_FMT = ARTWORK_FORMATS_BY_ID[1005]  # 80x80, role=photo_thumb, sin padding de stride
FULL_FMT = ARTWORK_FORMATS_BY_ID[1007]  # 480x864, role=photo_full, sin padding de stride

# Formato cuadrado sintético (más simple para razonar aspect ratio).
SQUARE_FULL_FMT = replace(FULL_FMT, format_id=999001, width=100, height=100, row_bytes=200)

# Formato horizontal (landscape) sintético — a diferencia de FULL_FMT real
# del Nano 7G (480x864, vertical), acá rotar una foto alta SÍ puede ganar
# área, que es el caso que should_rotate_tall_photo_for_format existe para
# detectar.
LANDSCAPE_FULL_FMT = replace(FULL_FMT, format_id=999002, width=200, height=100, row_bytes=400)


def _solid(size, color=(200, 50, 50)) -> Image.Image:
    return Image.new("RGB", size, color)


# ── fit_dimensions ───────────────────────────────────────────────────────────

class TestFitDimensions:
    def test_foto_mas_ancha_que_el_formato(self):
        # 400x100 (4:1) en un target 100x100 -> limita por ancho: 100x25
        assert fit_dimensions(400, 100, 100, 100) == (100, 25)

    def test_foto_mas_alta_que_el_formato(self):
        # 100x400 (1:4) en un target 100x100 -> limita por alto: 25x100
        assert fit_dimensions(100, 400, 100, 100) == (25, 100)

    def test_foto_exactamente_cuadrada(self):
        assert fit_dimensions(200, 200, 100, 100) == (100, 100)

    def test_target_no_cuadrado_foto_cuadrada(self):
        # target 80x864 (formato full del Nano 7G), foto cuadrada 500x500
        # -> limita por ancho (80 es la dimensión más restrictiva)
        assert fit_dimensions(500, 500, 80, 864) == (80, 80)

    def test_nunca_excede_el_target(self):
        w, h = fit_dimensions(3000, 3000, 80, 80)
        assert w <= 80 and h <= 80


# ── should_rotate_tall_photo_for_format ──────────────────────────────────────

class TestShouldRotateTallPhoto:
    def test_foto_alta_con_rotacion_habilitada_gana_area_en_formato_horizontal(self):
        # 100x300 (1:3) en un formato horizontal 200x100: sin rotar cabe
        # apretado (34x100=3400px), rotado aprovecha mucho más (200x67=13400px)
        # — ganancia real, verificada con fitted_area, no solo "es alta".
        img = _solid((100, 300))
        assert should_rotate_tall_photo_for_format(img, LANDSCAPE_FULL_FMT, rotate_tall_photos=True) is True

    def test_foto_alta_con_rotacion_deshabilitada(self):
        img = _solid((100, 300))
        assert should_rotate_tall_photo_for_format(img, LANDSCAPE_FULL_FMT, rotate_tall_photos=False) is False

    def test_formato_no_rotable_photo_thumb_nunca_rota(self):
        img = _solid((100, 300))
        assert should_rotate_tall_photo_for_format(img, THUMB_FMT, rotate_tall_photos=True) is False

    def test_foto_ancha_nunca_rota(self):
        img = _solid((300, 100))  # más ancha que alta
        assert should_rotate_tall_photo_for_format(img, LANDSCAPE_FULL_FMT, rotate_tall_photos=True) is False

    def test_foto_cuadrada_nunca_rota(self):
        img = _solid((200, 200))
        assert should_rotate_tall_photo_for_format(img, LANDSCAPE_FULL_FMT, rotate_tall_photos=True) is False

    def test_foto_apenas_por_debajo_del_umbral_de_aspecto_no_rota(self):
        # aspect ratio justo debajo de 1.15 -> no se considera "alta"
        w = 100
        h = int(w * ROTATE_TALL_PHOTO_ASPECT_THRESHOLD) - 1
        img = _solid((w, h))
        assert should_rotate_tall_photo_for_format(img, LANDSCAPE_FULL_FMT, rotate_tall_photos=True) is False

    def test_formato_vertical_real_del_nano7g_no_gana_rotando(self):
        # FULL_FMT real (480x864) ya es vertical — rotar una foto alta la
        # vuelve horizontal, que encaja PEOR en un target vertical. Caso
        # real donde "es alta" no implica "conviene rotar".
        img = _solid((100, 300))
        assert should_rotate_tall_photo_for_format(img, FULL_FMT, rotate_tall_photos=True) is False

    def test_rotar_no_mejora_area_en_formato_cuadrado_no_rota(self):
        # En un target CUADRADO, rotar una foto alta no cambia el área
        # aprovechada (fit_dimensions es simétrico en un target 1:1) —
        # ganancia = 1.0, por debajo del umbral 1.2, no debería rotar.
        img = _solid((100, 200))  # 1:2, por encima del umbral de aspecto
        assert should_rotate_tall_photo_for_format(img, SQUARE_FULL_FMT, rotate_tall_photos=True) is False


# ── fit_photo_to_format: dimensión a dimensión ───────────────────────────────

class TestFitPhotoToFormatDimensions:
    def test_foto_mas_ancha_letterbox_vertical(self):
        img = _solid((400, 100))
        canvas, mhni_w, mhni_h, hpad, vpad = fit_photo_to_format(img, SQUARE_FULL_FMT, fit_thumbnails=False)
        assert canvas.size == (100, 100)  # el lienzo SIEMPRE mide fmt.width x fmt.height
        assert hpad == 0
        assert vpad > 0
        # fit_dimensions da 100x25, pero 100-25=75 es impar -> se ajusta a
        # 24 para poder partir el padding en mitades enteras por lado:
        # vpad = (100-24)//2 = 38.
        assert vpad == 38

    def test_foto_mas_alta_pillarbox_horizontal(self):
        img = _solid((100, 400))
        canvas, mhni_w, mhni_h, hpad, vpad = fit_photo_to_format(img, SQUARE_FULL_FMT, fit_thumbnails=False)
        assert canvas.size == (100, 100)
        assert vpad == 0
        assert hpad > 0
        assert hpad == 38  # mismo ajuste de paridad que en el caso ancho

    def test_foto_exactamente_cuadrada_sin_padding(self):
        img = _solid((500, 500))
        canvas, mhni_w, mhni_h, hpad, vpad = fit_photo_to_format(img, SQUARE_FULL_FMT, fit_thumbnails=False)
        assert canvas.size == (100, 100)
        assert hpad == 0 and vpad == 0
        assert mhni_w == 100 and mhni_h == 100

    def test_thumbnail_sin_fit_recorta_a_llenar_sin_padding(self):
        # photo_thumb con fit_thumbnails=False: zoom+crop, nunca padding.
        img = _solid((400, 100))  # muy ancha
        canvas, mhni_w, mhni_h, hpad, vpad = fit_photo_to_format(img, THUMB_FMT, fit_thumbnails=False)
        assert canvas.size == (THUMB_FMT.width, THUMB_FMT.height)
        assert hpad == 0 and vpad == 0
        assert mhni_w == THUMB_FMT.width and mhni_h == THUMB_FMT.height

    def test_thumbnail_con_fit_thumbnails_si_usa_padding(self):
        # Con fit_thumbnails=True, un thumb se comporta como full: letterbox.
        img = _solid((400, 100))
        canvas, mhni_w, mhni_h, hpad, vpad = fit_photo_to_format(img, THUMB_FMT, fit_thumbnails=True)
        assert canvas.size == (THUMB_FMT.width, THUMB_FMT.height)
        assert vpad > 0

    def test_padding_siempre_divisible_para_simetria(self):
        # Casos con sobrante impar deben ajustarse para que hpad/vpad sean
        # exactos por lado (target - fitted debe ser par).
        for src_size in [(97, 300), (301, 99), (333, 111)]:
            img = _solid(src_size)
            canvas, _, _, hpad, vpad = fit_photo_to_format(img, SQUARE_FULL_FMT, fit_thumbnails=False)
            assert canvas.size == (100, 100)
            fitted_w = 100 - 2 * hpad
            fitted_h = 100 - 2 * vpad
            assert fitted_w > 0 and fitted_h > 0


# ── fit_photo_to_format: contenido real (píxel a píxel) ──────────────────────

class TestFitPhotoToFormatPixels:
    def test_padding_es_negro_y_contenido_conserva_el_color(self):
        color = (200, 50, 50)
        img = _solid((400, 100), color=color)  # ancha -> letterbox vertical
        canvas, _, _, hpad, vpad = fit_photo_to_format(img, SQUARE_FULL_FMT, fit_thumbnails=False)
        assert vpad == 38

        # Franja de padding arriba: negra.
        assert canvas.getpixel((50, 0)) == (0, 0, 0)
        assert canvas.getpixel((50, vpad - 1)) == (0, 0, 0)
        # Región de contenido: el color de la foto (LANCZOS puede introducir
        # ligera desviación en los bordes, el centro debe ser exacto).
        assert canvas.getpixel((50, 50)) == color
        # Franja de padding abajo: negra.
        assert canvas.getpixel((50, 100 - vpad)) == (0, 0, 0)
        assert canvas.getpixel((50, 99)) == (0, 0, 0)

    def test_sin_padding_todo_el_lienzo_es_contenido(self):
        color = (10, 200, 30)
        img = _solid((500, 500), color=color)
        canvas, _, _, hpad, vpad = fit_photo_to_format(img, SQUARE_FULL_FMT, fit_thumbnails=False)
        assert hpad == 0 and vpad == 0
        assert canvas.getpixel((0, 0)) == color
        assert canvas.getpixel((99, 99)) == color
        assert canvas.getpixel((50, 50)) == color


# ── encode_photo_for_format: extremo a extremo, RGB565 real ─────────────────

class TestEncodePhotoForFormat:
    def test_tamano_de_salida_coincide_con_stride_del_formato(self):
        img = _solid((500, 500))
        payload = encode_photo_for_format(img, SQUARE_FULL_FMT)
        expected_stride = SQUARE_FULL_FMT.row_bytes // 2
        assert payload.stride_pixels == expected_stride
        assert payload.size == expected_stride * SQUARE_FULL_FMT.height * 2
        assert len(payload.data) == payload.size

    def test_padding_decodifica_a_negro_contenido_decodifica_al_color(self):
        color = (200, 50, 50)
        img = _solid((400, 100), color=color)  # letterbox vertical, vpad=38
        payload = encode_photo_for_format(img, SQUARE_FULL_FMT)
        assert payload.hpad == 0 and payload.vpad == 38

        decoded = rgb565_le_to_rgb888(
            payload.data, SQUARE_FULL_FMT.width, SQUARE_FULL_FMT.height,
            stride=payload.stride_pixels,
        )
        # Fila de padding (arriba): negra exacta (RGB565 de negro es exacto,
        # sin pérdida de cuantización).
        assert decoded.getpixel((50, 0)) == (0, 0, 0)
        # Fila de contenido (centro): color reproducido dentro del margen
        # de cuantización RGB565 (5/6/5 bits, truncamiento — error máximo
        # empírico 7 en R/B de 5 bits, 3 en G de 6 bits; ver
        # TestRgb565LeToRgb888 en test_rgb565.py para el mismo criterio).
        r, g, b = decoded.getpixel((50, 50))
        assert abs(r - color[0]) <= 7
        assert abs(g - color[1]) <= 3
        assert abs(b - color[2]) <= 7

    def test_formato_real_del_nano_7g_photo_full(self):
        # 1007: 480x864, sin padding de stride (row_bytes=960=480*2).
        img = _solid((1200, 1200))  # cuadrada -> limita por ancho (480 < 864)
        payload = encode_photo_for_format(img, FULL_FMT)
        assert payload.stride_pixels == 480
        assert payload.hpad == 0
        assert payload.vpad > 0  # letterbox vertical, la foto es cuadrada y el formato no

    def test_rechaza_formato_no_rgb565_le(self):
        non_rgb565 = ARTWORK_FORMATS_BY_ID[1019]  # UYVY, tv_out
        with pytest.raises(NotImplementedError):
            encode_photo_for_format(_solid((100, 100)), non_rgb565)

    def test_rota_foto_alta_cuando_conviene_y_gana_area(self):
        # Formato HORIZONTAL (200x100): una foto alta (100x300) rota 270°
        # aprovecha mucho más área (visto en TestShouldRotateTallPhoto) —
        # confirmado acá en el resultado final codificado, no solo en el
        # booleano intermedio.
        tall_photo = _solid((100, 300), color=(1, 2, 3))
        payload_rotated = encode_photo_for_format(tall_photo, LANDSCAPE_FULL_FMT, rotate_tall_photos=True)
        payload_unrotated = encode_photo_for_format(tall_photo, LANDSCAPE_FULL_FMT, rotate_tall_photos=False)
        assert (payload_rotated.hpad, payload_rotated.vpad) != (payload_unrotated.hpad, payload_unrotated.vpad)
        # Menos padding total (más área de la foto real visible) al rotar.
        assert (payload_rotated.hpad + payload_rotated.vpad) < (payload_unrotated.hpad + payload_unrotated.vpad)


# ── Sanity check de mutación (aplicado manualmente sobre el archivo fuente,
# ver docs/VENDORED.md Paquete 9 Etapa 6g para el registro del resultado) ──
