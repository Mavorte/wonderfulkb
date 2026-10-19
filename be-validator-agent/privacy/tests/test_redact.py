import io
import os

import numpy as np
import pytest
from PIL import Image

pymupdf = pytest.importorskip("pymupdf")

from signature_privacy import (Region, changed_outside, conservative_regions, redact_pdf, redact_png, verify_redacted)  # noqa: E402

from conftest import png, scribble  # noqa: E402

W, H = 595, 842          # A4 v bodech


def noisy_signature(seed=1):
    """Výřez podpisu se šumem, aby jeho datový proud byl jedinečný a šel dohledat."""
    img = scribble(seed, size=(300, 100))
    arr = np.asarray(img).copy()
    rng = np.random.default_rng(seed)
    arr = np.clip(arr.astype(int) + rng.integers(-3, 4, arr.shape), 0, 255).astype(np.uint8)
    return png(Image.fromarray(arr))


def make_pdf(sig_in_label_zone=True, hidden_far=False):
    """Stránka: odstavec, popisek „Za dlužníka“ s podpisem (obrázek + vektorová čára + text SECRET pod boxem),
    nesouvisející obrázek (logo) a volitelně schovaný podpis daleko od popisku."""
    doc = pymupdf.open()
    page = doc.new_page(width=W, height=H)
    page.insert_text((50, 80), "Smlouva o uveru, odstavec s textem, ktery musi zustat.", fontsize=11)
    page.insert_image(pymupdf.Rect(50, 20, 110, 45), stream=png(scribble(9, size=(120, 50))))   # logo
    if sig_in_label_zone:
        page.insert_image(pymupdf.Rect(60, 600, 220, 650), stream=noisy_signature(1))
        shape = page.new_shape()
        shape.draw_bezier((70, 660), (110, 640), (150, 680), (200, 655))
        shape.finish(color=(0, 0, 0.4), width=1.5)
        shape.commit()
        page.insert_text((70, 625), "SECRET", fontsize=10)
        page.insert_text((60, 700), "Za dluznika", fontsize=10)
    if hidden_far:
        page.insert_image(pymupdf.Rect(300, 300, 460, 350), stream=noisy_signature(2))
    return doc.tobytes()


DET = [{"page": 1, "bbox": [60 / W, 600 / H, 220 / W, 650 / H]}]


def words(pdf, clip=None):
    d = pymupdf.open(stream=pdf, filetype="pdf")
    return [w[4] for w in d[0].get_text("words", clip=clip)]


def test_full_redaction_removes_content_and_passes_verification():
    src = make_pdf()
    regions = [Region(1, tuple(DET[0]["bbox"]), "full")]
    red = redact_pdf(src, regions)
    assert verify_redacted(src, red, regions) == []
    assert "SECRET" not in words(red)
    assert "odstavec" in words(red) and "Za" in words(red)            # ostatní text zůstal
    # logo mimo oblast přežilo
    assert len(pymupdf.open(stream=red, filetype="pdf")[0].get_image_info()) >= 1


def test_original_image_bytes_are_gone_from_file():
    src = make_pdf()
    needle = noisy_signature(1)
    red = redact_pdf(src, [Region(1, tuple(DET[0]["bbox"]), "full")])
    assert b"SECRET" not in red
    d = pymupdf.open(stream=red, filetype="pdf")
    pix_sig = [d.extract_image(x)["image"] for x in range(1, d.xref_length()) if _is_image(d, x)]
    assert needle not in pix_sig and all(needle not in p for p in pix_sig)


def _is_image(doc, x):
    try:
        return doc.xref_get_key(x, "Subtype")[1] == "/Image"
    except Exception:  # noqa: BLE001
        return False


def test_verification_fails_on_unredacted_file():
    """Test umí selhat: bez redakce ohlásí zbylý obrázek, text i neprázdnou oblast."""
    src = make_pdf()
    problems = verify_redacted(src, src, [Region(1, tuple(DET[0]["bbox"]), "full")])
    assert any("obrázek" in p for p in problems) and any("text" in p for p in problems)


def test_verification_fails_on_overlay_only():
    """Pouhé překrytí černým obdélníkem (obsah zůstane pod ním) redakcí není."""
    src = make_pdf()
    d = pymupdf.open(stream=src, filetype="pdf")
    d[0].draw_rect(pymupdf.Rect(55, 595, 225, 655), color=(0, 0, 0), fill=(0, 0, 0))
    overlay = d.tobytes()
    problems = verify_redacted(src, overlay, [Region(1, tuple(DET[0]["bbox"]), "full")])
    assert problems


def test_conservative_zone_removes_undetected_signature_but_keeps_text():
    """Podpis, který detektor nenašel, ale leží nad popiskem „Za dluznika“, se odstraní; text zůstane."""
    src = make_pdf()
    regions = conservative_regions(src, [])                # žádný nález
    assert any(r.source == "label" and r.mode == "graphics" for r in regions)
    red = redact_pdf(src, regions)
    assert verify_redacted(src, red, regions) == []
    assert "SECRET" in words(red) and "odstavec" in words(red)
    d = pymupdf.open(stream=red, filetype="pdf")
    assert not [x for x in d[0].get_drawings() if pymupdf.Rect(x["rect"]).intersects(pymupdf.Rect(60, 600, 220, 680))]


def test_residual_risk_signature_outside_every_region_survives():
    """Zbytkové riziko: podpis mimo nález i zóny zůstává v souboru. Test to hlídá, ať se neslibuje víc."""
    src = make_pdf(hidden_far=True)
    regions = conservative_regions(src, DET)
    red = redact_pdf(src, regions)
    d = pymupdf.open(stream=red, filetype="pdf")
    far = [i for i in d[0].get_image_info() if pymupdf.Rect(i["bbox"]).intersects(pymupdf.Rect(300, 300, 460, 350))]
    assert far, "nepokrytý podpis by měl zůstat (jinak redakce maže víc, než má)"


def test_scanned_page_pixels_are_blacked_out():
    """Sken = celá strana je jeden obrázek: přepíšou se pixely jen v oblasti."""
    page_img = Image.new("RGB", (W * 2, H * 2), "white")
    page_img.paste(scribble(3, size=(320, 100)), (140, 1200))
    doc = pymupdf.open()
    p = doc.new_page(width=W, height=H)
    p.insert_image(p.rect, stream=png(page_img))
    src = doc.tobytes()
    regions = [Region(1, (60 / W, 595 / H, 225 / W, 655 / H), "full")]
    red = redact_pdf(src, regions)
    assert verify_redacted(src, red, regions) == []
    d = pymupdf.open(stream=red, filetype="pdf")
    pix = d[0].get_pixmap(dpi=100, clip=pymupdf.Rect(70, 605, 215, 650), colorspace=pymupdf.csGRAY)
    assert np.frombuffer(pix.samples, np.uint8).mean() < 8


def test_collateral_damage_is_detected():
    src = make_pdf()
    regions = [Region(1, tuple(DET[0]["bbox"]), "full")]
    red = redact_pdf(src, regions + [Region(1, (0.05, 0.05, 0.9, 0.12), "full")])      # smaže i odstavec
    assert not changed_outside(src, redact_pdf(src, regions), regions) or \
        max(changed_outside(src, redact_pdf(src, regions), regions).values()) < 0.002
    assert max(changed_outside(src, red, regions).values()) > 0.002


def test_redact_png_blacks_box_only():
    img = Image.new("RGB", (200, 100), "white")
    out = np.asarray(Image.open(io.BytesIO(redact_png(png(img), [(0.25, 0.25, 0.5, 0.5)]))).convert("L"))
    assert out[40:45, 60:90].max() == 0 and out[90, 190] == 255
