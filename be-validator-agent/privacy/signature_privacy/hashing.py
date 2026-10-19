"""Percepční hash výřezu: jednosměrný, jen na detekci kopie.

Stejný postup jako `phash_and_mask` v `signatures/signature_pipeline/imaging.py` (maska inkoustu, ořez na
inkoust, DCT 32×32, 64 bitů, hex 16 znaků), takže hodnoty z obou modulů jsou srovnatelné.
64 bitů nejde převést zpět na obrázek (nese jen znaménka 63 nízkých frekvencí); slouží pro Hammingovu
vzdálenost, ne pro zobrazení.
"""
import io

import numpy as np
from PIL import Image

from .errors import PrivacyError

HASH_SIZE = 32
HASH_LOW = 8
MIN_INK_PIXELS = 30
RULE_FRACTION = 0.85
MAX_PIXELS = 50_000_000


def _dct_matrix(n):
    k = np.arange(n)[:, None]
    i = np.arange(n)[None, :]
    m = np.cos(np.pi * (2 * i + 1) * k / (2 * n)) * np.sqrt(2 / n)
    m[0] /= np.sqrt(2)
    return m


_DCT = _dct_matrix(HASH_SIZE)


def _ink_mask(image):
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    ink = gray < np.percentile(gray, 90) - 60
    h, w = ink.shape
    ink[ink.sum(axis=1) > RULE_FRACTION * w, :] = False
    ink[:, ink.sum(axis=0) > RULE_FRACTION * h] = False
    if ink.sum() < MIN_INK_PIXELS:
        return None
    ys, xs = np.where(ink)
    return ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def phash(png_bytes: bytes) -> str | None:
    """Hex řetězec 16 znaků, nebo None pro (téměř) prázdný výřez."""
    try:
        img = Image.open(io.BytesIO(png_bytes))
        if img.width * img.height > MAX_PIXELS:
            raise PrivacyError("Obrázek je příliš velký")
        img = img.convert("RGB")
    except PrivacyError:
        raise
    except Exception:  # noqa: BLE001
        raise PrivacyError("Vstup není čitelný obrázek") from None
    mask = _ink_mask(img)
    if mask is None:
        return None
    ink = mask.astype(np.float32)
    small = np.asarray(Image.fromarray((ink * 255).astype(np.uint8)).resize((HASH_SIZE, HASH_SIZE), Image.LANCZOS),
                       dtype=np.float32) / 255.0
    low = (_DCT @ small @ _DCT.T)[:HASH_LOW, :HASH_LOW].flatten()
    bits = np.concatenate([[False], low[1:] > np.median(low[1:])])
    return f"{int(''.join('1' if b else '0' for b in bits), 2):016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")
