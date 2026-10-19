"""Živý test KmsKeyProvider proti skutečnému KMS klíči (jen syntetická data, nic se nikam nezapisuje).

    AWS_PROFILE=hackathon PRIVACY_KMS_KEY_ID=alias/wonderfulkb-signatures python live_check.py

Volá GenerateDataKey a Decrypt (2 až 6 požadavků na KMS). Šifrovaný blok zůstává v paměti."""
import io
import os
import random
import sys
import time

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from signature_privacy import (DecryptionError, KmsKeyProvider, SignatureContext, decrypt_image, distorted_preview,
                               encrypt_image, is_encrypted_blob)


def synthetic_png():
    rnd = random.Random(7)
    img = Image.new("RGB", (400, 140), "white")
    pts = [(20 + i * 18, 70 + rnd.randint(-40, 40)) for i in range(20)]
    ImageDraw.Draw(img).line(pts, fill=(10, 10, 60), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main():
    provider = KmsKeyProvider()                     # PRIVACY_KMS_KEY_ID, jinak alias/wonderfulkb-signatures
    print("klíč:", provider.key_id)
    png = synthetic_png()
    ctx = SignatureContext("live-check-case", "live-check-doc", "sig_01")
    t = time.perf_counter()
    blob = encrypt_image(png, ctx, provider)
    t_enc = time.perf_counter() - t
    assert is_encrypted_blob(blob) and png not in blob
    t = time.perf_counter()
    assert decrypt_image(blob, ctx, provider) == png
    t_dec = time.perf_counter() - t
    print(f"round-trip OK; encrypt {t_enc * 1000:.0f} ms, decrypt {t_dec * 1000:.0f} ms, blok {len(blob)} B")
    for field in ("case_id", "document_id", "signature_id"):
        try:
            decrypt_image(blob, ctx._replace(**{field: ctx._asdict()[field] + "x"}), provider)
            print("CHYBA: jiný", field, "prošel")
            sys.exit(1)
        except DecryptionError:
            print(f"jiný {field}: odmítnuto OK")
    assert distorted_preview(png)
    print("hotovo")


if __name__ == "__main__":
    main()
