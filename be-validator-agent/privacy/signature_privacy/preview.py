"""Zkreslený náhled: smí se ukazovat bez odkrytí, podpis z něj nejde přečíst ani okopírovat.

Postup: šedá, průměr do hrubé mřížky (výchozí nejvýš 10 buněk na šířku), nové rozmezí jasu, hladké zvětšení
a rozmazání. Z původního obrázku zůstane jen hrubé rozložení inkoustu (kolik inkoustu je kde), tahy, tvar
písmen, sklon ani tloušťka čáry ne. Náhled se z obrázku počítá deterministicky, aby ho šlo ukládat jako
obyčejný soubor.
"""
import io

import numpy as np
from PIL import Image, ImageFilter

from .errors import PrivacyError

GRID_WIDTH = 10         # buněk na šířku
MIN_GRID = 2
OUT_WIDTH = 240         # šířka výsledku v pixelech
MAX_PIXELS = 50_000_000
DARKEST = 90            # nejtmavší buňka (0 = černá): náhled nikdy nepůsobí jako černý inkoust


def _open(png_bytes: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(png_bytes))
        if img.width * img.height > MAX_PIXELS:
            raise PrivacyError("Obrázek je příliš velký")
        img.load()
    except PrivacyError:
        raise
    except Exception:  # noqa: BLE001
        raise PrivacyError("Vstup není čitelný obrázek") from None
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img)
    return img.convert("L")


def distorted_preview(png_bytes: bytes, grid_width: int = GRID_WIDTH, out_width: int = OUT_WIDTH) -> bytes:
    """PNG se zkresleným náhledem téhož výřezu (stejný poměr stran)."""
    gray = _open(png_bytes)
    w, h = gray.size
    gw = max(MIN_GRID, min(grid_width, w))
    gh = max(MIN_GRID, min(round(gw * h / w), gw * 2, h))
    cells = np.asarray(gray.resize((gw, gh), Image.BOX), dtype=np.float32)
    lo, hi = float(cells.min()), float(cells.max())
    if hi - lo > 1e-3:
        cells = (cells - lo) / (hi - lo)               # 0 = nejvíc inkoustu, 1 = nejméně
        cells = DARKEST + cells * (255 - DARKEST)
    else:
        cells = np.full_like(cells, 255.0)             # prázdný výřez zůstane světlý
    small = Image.fromarray(np.clip(cells, 0, 255).astype(np.uint8), "L")
    out_h = max(1, round(out_width * h / w))
    big = small.resize((out_width, out_h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(radius=out_width / gw / 2))
    buf = io.BytesIO()
    big.save(buf, format="PNG")
    return buf.getvalue()
