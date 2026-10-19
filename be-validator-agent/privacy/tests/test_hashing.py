import pytest
from PIL import Image

from signature_privacy import PrivacyError, hamming, phash

from conftest import png, scribble


def test_phash_format_and_stability(sig_png):
    h = phash(sig_png)
    assert len(h) == 16 and int(h, 16) >= 0
    assert phash(sig_png) == h


def test_phash_detects_copy_and_ignores_shift_and_scale():
    base = scribble(1)
    shifted = Image.new("RGB", (base.width + 60, base.height + 40), "white")
    shifted.paste(base, (35, 25))
    assert hamming(phash(png(base)), phash(png(shifted))) <= 8
    assert hamming(phash(png(base)), phash(png(base.resize((200, 70))))) <= 10


def test_phash_differs_for_other_signatures():
    assert min(hamming(phash(png(scribble(1))), phash(png(scribble(s)))) for s in range(2, 8)) > 8


def test_phash_blank_is_none():
    assert phash(png(Image.new("RGB", (200, 80), "white"))) is None


def test_phash_is_not_invertible_in_size(sig_png):
    """Hash má 64 bitů: z originálu o desítkách tisíc pixelů se nedá obnovit."""
    assert len(bytes.fromhex(phash(sig_png))) == 8


def test_phash_rejects_garbage():
    with pytest.raises(PrivacyError):
        phash(b"x")


def test_phash_matches_signatures_module():
    """Shoda s `phash_and_mask` z modulu podpisů (kontrola kompatibility; bez PyMuPDF se přeskočí)."""
    import sys
    from pathlib import Path
    pytest.importorskip("pymupdf")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "signatures"))
    try:
        from signature_pipeline.imaging import phash_and_mask
    except Exception:  # noqa: BLE001
        pytest.skip("modul podpisů není importovatelný")
    for seed in range(1, 5):
        img = scribble(seed)
        assert phash(png(img)) == phash_and_mask(img)[0]
