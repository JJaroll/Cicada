"""Conversión de carátulas a RGB565 little-endian para ithmb.

Adaptado de artworkdb_writer/rgb565.py de iOpenPod (ver docs/VENDORED.md,
Paquete 7, Etapa 4b). Acotado a RGB565_LE — el único pixel_format que usan
los 4 formatos del Nano 7G (cicada.ipod.device.artwork_presets). Los demás
formatos de iOpenPod (RGB565_BE, RGB555, UYVY, JPEG) no se portan aquí; ver
Etapa 4f en docs/IPOD_INTEGRATION.md.

RGB565: 5 bits rojo | 6 bits verde | 5 bits azul (16 bits por píxel).
"""
from __future__ import annotations

import io
from typing import Optional

import numpy as np
from PIL import Image

from cicada.ipod.db.artwork.types import EncodedFormatPayload
from cicada.ipod.device.artwork_presets import ArtworkFormat

BYTES_PER_PIXEL = 2


def image_from_bytes(art_bytes: bytes) -> Optional[Image.Image]:
    """Decodifica bytes de imagen (JPEG/PNG/etc) a un PIL.Image en modo RGB."""
    try:
        img = Image.open(io.BytesIO(art_bytes))
        if img.mode != "RGB":
            img = img.convert("RGBA").convert("RGB")
        return img
    except Image.DecompressionBombError:
        return None
    except Exception:
        return None


def resize_for_format(img: Image.Image, fmt: ArtworkFormat) -> Image.Image:
    """Redimensiona a las dimensiones exactas del formato, sin preservar aspecto.

    La carátula es cuadrada por convención; redimensionar directo al tamaño
    destino (sin letterbox) es el mismo comportamiento que usa iTunes.
    """
    return img.resize((fmt.width, fmt.height), Image.Resampling.LANCZOS)


def rgb888_to_rgb565_le(
    img: Image.Image, width: int, height: int, stride: Optional[int] = None
) -> bytes:
    """Convierte una imagen RGB888 a bytes RGB565 little-endian.

    La imagen debe medir exactamente width x height (garantizado por
    resize_for_format). Si stride > width, cada fila se rellena con
    píxeles a cero hasta llegar a stride (alineación que exige el formato
    1016 del Nano 7G, por ejemplo).
    """
    if stride is None:
        stride = width

    arr = np.array(img, dtype=np.uint32)
    actual_h, actual_w = arr.shape[:2]
    if actual_w != width or actual_h != height:
        raise ValueError(f"Imagen {actual_w}x{actual_h} != esperado {width}x{height}")

    r = (arr[:, :, 0] >> 3) & 0x1F
    g = (arr[:, :, 1] >> 2) & 0x3F
    b = (arr[:, :, 2] >> 3) & 0x1F
    rgb565 = ((r << 11) | (g << 5) | b).astype(np.uint16)

    if stride > width:
        padded = np.zeros((height, stride), dtype=np.uint16)
        padded[:, :width] = rgb565
        rgb565 = padded

    return rgb565.astype("<u2").tobytes()


def rgb565_le_to_rgb888(data: bytes, width: int, height: int, stride: Optional[int] = None) -> Image.Image:
    """Inversa de rgb888_to_rgb565_le — solo para verificación/inspección.

    No hace falta en el camino de escritura (Cicada no preserva/decodifica
    arte existente, Etapa 4c), pero sí para comprobar en staging que un
    .ithmb generado, releído y decodificado reproduce los píxeles
    originales (dentro del margen de pérdida de la cuantización RGB565).
    """
    if stride is None:
        stride = width

    arr = np.frombuffer(data, dtype="<u2").reshape((height, stride))[:, :width]
    r = ((arr >> 11) & 0x1F).astype(np.uint8)
    g = ((arr >> 5) & 0x3F).astype(np.uint8)
    b = (arr & 0x1F).astype(np.uint8)
    r8 = (r << 3) | (r >> 2)
    g8 = (g << 2) | (g >> 4)
    b8 = (b << 3) | (b >> 2)
    return Image.fromarray(np.dstack([r8, g8, b8]), mode="RGB")


def convert_art_for_format(art_bytes: bytes, fmt: ArtworkFormat) -> Optional[EncodedFormatPayload]:
    """Decodifica + redimensiona + codifica arte para un ArtworkFormat concreto.

    Devuelve None si art_bytes no se pudo decodificar como imagen. Lanza
    NotImplementedError si el formato no es RGB565_LE (fuera de alcance
    hasta la Etapa 4f) en vez de producir bytes silenciosamente incorrectos.
    """
    if fmt.pixel_format != "RGB565_LE":
        raise NotImplementedError(
            f"pixel_format {fmt.pixel_format!r} (format_id={fmt.format_id}) no soportado "
            "todavía — solo RGB565_LE (Nano 7G) hasta la Etapa 4f."
        )

    img = image_from_bytes(art_bytes)
    if img is None:
        return None

    resized = resize_for_format(img, fmt)
    stride_pixels = fmt.row_bytes // BYTES_PER_PIXEL
    data = rgb888_to_rgb565_le(resized, fmt.width, fmt.height, stride=stride_pixels)
    hpad = stride_pixels - fmt.width

    return EncodedFormatPayload(
        data=data,
        width=fmt.width,
        height=fmt.height,
        size=len(data),
        stride_pixels=stride_pixels,
        hpad=hpad,
        vpad=0,
        pixel_format=fmt.pixel_format,
    )
