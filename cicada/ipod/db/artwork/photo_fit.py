"""Fit/pad/rotate de fotos a un ``ArtworkFormat`` de Fotos (Fase 6, Etapa 6g).

Adaptado de ``_fit_dimensions``/``_fitted_area``/
``_should_rotate_tall_photo_for_format``/``_fit_photo_to_format`` en
``sync/photos.py`` de iOpenPod (ver docs/VENDORED.md, Paquete 9).

Bloque aislado a propósito, sin mezclarse con el coordinador (Etapa 6h):
esta es la lógica con superficie de error real (aspect ratio, padding
simétrico, rotación condicional) — si algo falla más adelante conviene
poder aislar si es esto o la orquestación, sin tener que separarlos
retroactivamente.

Reusa :func:`cicada.ipod.db.artwork.rgb565.rgb888_to_rgb565_le` sin
cambios — el codec de empaquetado de píxeles ya era agnóstico a la
política de resize (confirmado en la investigación de Fotos). Lo que
faltaba era esta política, no el codec. A diferencia de
``resize_for_format()`` (cover art, Etapa 4b): **nunca estira sin
preservar aspecto** — una carátula cuadrada tolera estirarse, una foto
real no.
"""
from __future__ import annotations

import math
from typing import Tuple

from PIL import Image

from cicada.ipod.db.artwork.rgb565 import BYTES_PER_PIXEL, rgb888_to_rgb565_le
from cicada.ipod.db.artwork.types import EncodedFormatPayload
from cicada.ipod.device.artwork_presets import ArtworkFormat

#: Roles de formato para los que la rotación condicional de fotos altas
#: tiene sentido — miniaturas (photo_thumb/photo_list) siempre recortan a
#: llenar, rotarlas no cambia nada.
ROTATABLE_PHOTO_ROLES = frozenset({"photo_full", "photo_preview", "photo_large", "tv_out"})

#: Roles que iTunes renderiza con zoom-and-crop-to-fill en vez de fit+pad.
THUMBNAIL_PHOTO_ROLES = frozenset({"photo_thumb", "photo_list"})

#: Umbral de aspect ratio (alto/ancho) para considerar una foto "alta".
ROTATE_TALL_PHOTO_ASPECT_THRESHOLD = 1.15

#: Rotar solo si el área aprovechada mejora al menos este factor.
ROTATE_TALL_PHOTO_GAIN_THRESHOLD = 1.2


def fit_dimensions(src_w: int, src_h: int, target_w: int, target_h: int) -> Tuple[int, int]:
    """Dimensiones que caben dentro de ``target_w``x``target_h`` preservando
    aspect ratio (letterbox, sin recortar)."""
    width_scale = target_w / src_w
    height_scale = target_h / src_h
    if width_scale < height_scale:
        fitted_w = target_w
        fitted_h = min(int(math.ceil(src_h * width_scale)), target_h)
    elif width_scale > height_scale:
        fitted_w = min(int(math.ceil(src_w * height_scale)), target_w)
        fitted_h = target_h
    else:
        fitted_w = target_w
        fitted_h = target_h
    return (
        max(1, min(target_w, fitted_w)),
        max(1, min(target_h, fitted_h)),
    )


def fitted_area(src_w: int, src_h: int, target_w: int, target_h: int) -> int:
    fitted_w, fitted_h = fit_dimensions(src_w, src_h, target_w, target_h)
    return fitted_w * fitted_h


def should_rotate_tall_photo_for_format(
    img: Image.Image,
    fmt: ArtworkFormat,
    rotate_tall_photos: bool,
) -> bool:
    """``True`` si rotar 270° una foto más alta que ancha aprovecha
    significativamente más área del formato destino. Nunca decide esto
    para miniaturas (que recortan a llenar de todos modos) ni si el
    llamador desactivó la rotación (``rotate_tall_photos=False``, default
    seguro — nadie pidió esto por defecto)."""
    if not rotate_tall_photos or fmt.role not in ROTATABLE_PHOTO_ROLES:
        return False
    src_w, src_h = img.size
    target_w = max(1, int(fmt.width))
    target_h = max(1, int(fmt.height))
    if src_w <= 0 or src_h <= 0 or src_h <= src_w:
        return False
    if (src_h / src_w) < ROTATE_TALL_PHOTO_ASPECT_THRESHOLD:
        return False

    normal_area = fitted_area(src_w, src_h, target_w, target_h)
    rotated_area = fitted_area(src_h, src_w, target_w, target_h)
    return rotated_area >= int(math.ceil(normal_area * ROTATE_TALL_PHOTO_GAIN_THRESHOLD))


def fit_photo_to_format(
    img: Image.Image,
    fmt: ArtworkFormat,
    *,
    fit_thumbnails: bool,
) -> Tuple[Image.Image, int, int, int, int]:
    """Ajusta ``img`` al lienzo exacto de ``fmt`` (``fmt.width``x``fmt.height``).

    Devuelve ``(canvas, mhni_width, mhni_height, hpad, vpad)`` — ``canvas``
    siempre mide exactamente ``fmt.width``x``fmt.height`` (listo para
    :func:`rgb888_to_rgb565_le`); ``mhni_width``/``mhni_height``/``hpad``/
    ``vpad`` son los valores a escribir en el MHNI (región visible +
    padding simétrico), no necesariamente iguales a ``fmt.width``/
    ``fmt.height``.

    Miniaturas (``THUMBNAIL_PHOTO_ROLES``) sin ``fit_thumbnails``: zoom y
    recorte para llenar el formato (comportamiento de iTunes). Todo lo
    demás: fit preservando aspecto + padding negro simétrico — nunca
    estira.
    """
    target_w = max(1, int(fmt.width))
    target_h = max(1, int(fmt.height))
    source = img.convert("RGB")
    src_w, src_h = source.size
    if src_w <= 0 or src_h <= 0:
        fallback = source.resize((target_w, target_h), Image.Resampling.LANCZOS)
        return fallback, target_w, target_h, 0, 0

    if fmt.role in THUMBNAIL_PHOTO_ROLES and not fit_thumbnails:
        fill_scale = max(target_w / src_w, target_h / src_h)
        fill_w = max(1, int(math.ceil(src_w * fill_scale)))
        fill_h = max(1, int(math.ceil(src_h * fill_scale)))
        filled = source.resize((fill_w, fill_h), Image.Resampling.LANCZOS)
        left = max(0, (fill_w - target_w) // 2)
        top = max(0, (fill_h - target_h) // 2)
        cropped = filled.crop((left, top, left + target_w, top + target_h))
        return cropped, target_w, target_h, 0, 0

    fitted_w, fitted_h = fit_dimensions(src_w, src_h, target_w, target_h)

    # El padding del MHNI de fotos es simétrico por lado — asegurar que el
    # sobrante se pueda partir en mitades enteras izquierda/derecha,
    # arriba/abajo.
    if fitted_w < target_w and ((target_w - fitted_w) % 2) != 0:
        fitted_w = max(1, fitted_w - 1)
    if fitted_h < target_h and ((target_h - fitted_h) % 2) != 0:
        fitted_h = max(1, fitted_h - 1)

    fitted = source.resize((fitted_w, fitted_h), Image.Resampling.LANCZOS)
    if fitted_w == target_w and fitted_h == target_h:
        return fitted, target_w, target_h, 0, 0

    hpad = max(0, (target_w - fitted_w) // 2)
    vpad = max(0, (target_h - fitted_h) // 2)
    canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
    canvas.paste(fitted, (hpad, vpad))

    visible_w = max(1, target_w - (2 * hpad))
    visible_h = max(1, target_h - (2 * vpad))
    mhni_width = visible_w + hpad
    mhni_height = visible_h + vpad
    return canvas, mhni_width, mhni_height, hpad, vpad


def encode_photo_for_format(
    img: Image.Image,
    fmt: ArtworkFormat,
    *,
    rotate_tall_photos: bool = False,
    fit_thumbnails: bool = False,
) -> EncodedFormatPayload:
    """Rota (si aplica) + ajusta + empaqueta ``img`` para un formato de
    Fotos concreto. Punto de entrada único de este módulo — compone
    :func:`should_rotate_tall_photo_for_format` + :func:`fit_photo_to_format`
    + :func:`rgb888_to_rgb565_le` (sin cambios).

    Como :func:`cicada.ipod.db.artwork.rgb565.convert_art_for_format`:
    lanza ``NotImplementedError`` si el formato no es RGB565_LE, en vez de
    producir bytes silenciosamente incorrectos — el Nano 7G solo usa
    RGB565_LE también para fotos (``photo_formats`` en ``capabilities.py``).
    """
    if fmt.pixel_format != "RGB565_LE":
        raise NotImplementedError(
            f"pixel_format {fmt.pixel_format!r} (format_id={fmt.format_id}) no soportado "
            "todavía para Fotos — solo RGB565_LE (Nano 7G)."
        )

    source = img
    if should_rotate_tall_photo_for_format(img, fmt, rotate_tall_photos):
        source = img.transpose(Image.Transpose.ROTATE_270)

    canvas, mhni_width, mhni_height, hpad, vpad = fit_photo_to_format(
        source, fmt, fit_thumbnails=fit_thumbnails,
    )

    stride_pixels = fmt.row_bytes // BYTES_PER_PIXEL
    data = rgb888_to_rgb565_le(canvas, fmt.width, fmt.height, stride=stride_pixels)

    return EncodedFormatPayload(
        data=data,
        width=mhni_width,
        height=mhni_height,
        size=len(data),
        stride_pixels=stride_pixels,
        hpad=hpad,
        vpad=vpad,
        pixel_format=fmt.pixel_format,
    )
