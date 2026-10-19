import io

import numpy as np
import pytest
from PIL import Image

from signature_privacy import PrivacyError, distorted_preview
from signature_privacy import preview as pv

from conftest import png, scribble


def gray(b):
    return np.asarray(Image.open(io.BytesIO(b)).convert("L"), dtype=np.float32)


def test_preview_is_png_with_same_aspect(sig_png):
    out = distorted_preview(sig_png)
    img = Image.open(io.BytesIO(out))
    assert img.format == "PNG" and img.width == pv.OUT_WIDTH
    assert abs(img.width / img.height - 400 / 140) < 0.05


def test_preview_is_deterministic(sig_png):
    assert distorted_preview(sig_png) == distorted_preview(sig_png)


def test_preview_loses_fine_detail(sig_png):
    """Původní obrázek má tahy s ostrými hranami; náhled nemá žádnou hranu, jen pozvolné přechody."""
    orig, prev = gray(sig_png), gray(distorted_preview(sig_png))
    assert np.abs(np.diff(orig, axis=1)).max() > 150
    assert np.abs(np.diff(prev, axis=1)).max() < 12


def test_preview_cannot_distinguish_strokes_within_a_cell():
    """Dva různé podpisy se stejným rozložením inkoustu po hrubých buňkách dají téměř stejný náhled.

    Druhý vznikne posunem každého pruhu o pár pixelů: tvar tahů je jiný, hrubé rozložení stejné."""
    a = np.full((140, 400), 255, np.uint8)
    b = a.copy()
    for i, x in enumerate(range(10, 390, 40)):            # buňka má 40 px; tah leží v různém místě buňky
        a[30:110, x + 5:x + 8] = 20
        b[30:110, x + 25:x + 28] = 20
        a[60 + i % 3:63 + i % 3, x:x + 40] = 20
        b[60 + 2 - i % 3:63 + 2 - i % 3, x:x + 40] = 20
    pa, pb = gray(distorted_preview(png(Image.fromarray(a)))), gray(distorted_preview(png(Image.fromarray(b))))
    assert np.abs(pa - pb).mean() < 6
    assert np.abs(gray(png(Image.fromarray(a))) - gray(png(Image.fromarray(b)))).mean() > 5   # originály se liší


def test_preview_information_is_only_a_coarse_grid(sig_png):
    """Náhled leží blízko jednoduché mřížky: zmenšený na mřížku a zpět se skoro nemění, tedy v něm nic víc není."""
    prev = Image.open(io.BytesIO(distorted_preview(sig_png))).convert("L")
    w, h = prev.size
    back = prev.resize((pv.GRID_WIDTH * 4, max(2, round(pv.GRID_WIDTH * 4 * h / w))), Image.BOX).resize((w, h), Image.BICUBIC)
    assert np.abs(np.asarray(prev, np.float32) - np.asarray(back, np.float32)).mean() < 6


def test_preview_never_black_and_blank_stays_light():
    blank = distorted_preview(png(Image.new("RGB", (300, 100), "white")))
    assert gray(blank).min() > 240
    assert gray(distorted_preview(png(scribble(3)))).min() >= pv.DARKEST - 15


def test_preview_handles_transparency_and_small_images():
    rgba = Image.new("RGBA", (5, 3), (0, 0, 0, 0))
    assert distorted_preview(png(rgba))


def test_preview_rejects_garbage():
    with pytest.raises(PrivacyError):
        distorted_preview(b"not an image")
