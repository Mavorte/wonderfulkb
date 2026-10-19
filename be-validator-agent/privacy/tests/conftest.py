import io
import os
import random

import numpy as np
import pytest
from PIL import Image, ImageDraw

from signature_privacy import LocalKeyProvider, SignatureContext

# Testy nikdy nesmí sáhnout na skutečný účet: přihlašovací údaje se přepíšou fiktivními.
for _k in ("AWS_PROFILE", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN", "PRIVACY_KMS_KEY_ID", "WKB_LOCAL_MASTER_KEY"):
    os.environ.pop(_k, None)
os.environ.update(AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing", AWS_DEFAULT_REGION="eu-central-1")


@pytest.fixture
def ctx():
    return SignatureContext("case-1", "doc-1", "sig_01")


@pytest.fixture
def provider():
    return LocalKeyProvider.generate()


def scribble(seed=1, size=(400, 140), width=3):
    """Syntetický „podpis“: náhodná lomená čára, tmavá na bílém."""
    rnd = random.Random(seed)
    img = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    x, y = 20, size[1] // 2
    pts = [(x, y)]
    while x < size[0] - 30:
        x += rnd.randint(8, 30)
        y = max(15, min(size[1] - 15, y + rnd.randint(-45, 45)))
        pts.append((x, y))
    d.line(pts, fill=(10, 10, 60), width=width, joint="curve")
    return img


def png(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sig_png():
    return png(scribble())
