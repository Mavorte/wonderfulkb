"""Volání Bedrocku: embeddingy textu a obrazu o 1024 dimenzích.

Model se vybírá proměnnými prostředí (výchozí je Titan, viz README a benchmark):
  EMBED_TEXT_MODEL   amazon.titan-embed-text-v2:0 | cohere.embed-v4:0
  EMBED_IMAGE_MODEL  amazon.titan-embed-image-v1  | cohere.embed-v4:0
Vektory různých modelů se nemíchají: `model` a `model_version` jdou do metadat každého vektoru
a `nearest_verified` ve výchozím stavu hledá jen vektory aktuálně nastaveného modelu.
"""
from __future__ import annotations

import base64
import io
import json
import os
from typing import NamedTuple

from PIL import Image

from . import clients

DIMENSION = 1024

TITAN_TEXT = "amazon.titan-embed-text-v2:0"
TITAN_IMAGE = "amazon.titan-embed-image-v1"
COHERE_V4 = "cohere.embed-v4:0"

# Cohere v4 jde v eu-central-1 volat jen přes inference profil; `eu.` drží data v EU.
INVOKE_ID = {COHERE_V4: "eu.cohere.embed-v4:0"}
MODEL_VERSION = {TITAN_TEXT: "v2", TITAN_IMAGE: "v1", COHERE_V4: "v4"}
TEXT_MODELS = (TITAN_TEXT, COHERE_V4)
IMAGE_MODELS = (TITAN_IMAGE, COHERE_V4)

# zpětně kompatibilní názvy (výchozí modely)
TEXT_MODEL, TEXT_MODEL_VERSION = TITAN_TEXT, MODEL_VERSION[TITAN_TEXT]
IMAGE_MODEL, IMAGE_MODEL_VERSION = TITAN_IMAGE, MODEL_VERSION[TITAN_IMAGE]

MAX_TEXT_CHARS = 50_000   # Titan Text v2: 8192 tokenů, 50 000 znaků (Cohere v4 má 128k tokenů)
IMAGE_MIN_SIDE = 128      # Titan Multimodal: strany 128 až 2048 px, soubor do 5 MB
IMAGE_MAX_SIDE = 1024
COHERE_TEXT_BATCH = 16    # Cohere bere až 96 textů na volání; držíme menší dávky


class ModelRef(NamedTuple):
    model: str
    version: str


def text_model() -> ModelRef:
    m = os.environ.get("EMBED_TEXT_MODEL") or TITAN_TEXT
    if m not in TEXT_MODELS:
        raise ValueError(f"EMBED_TEXT_MODEL={m!r}, podporováno {TEXT_MODELS}")
    return ModelRef(m, MODEL_VERSION[m])


def image_model() -> ModelRef:
    m = os.environ.get("EMBED_IMAGE_MODEL") or TITAN_IMAGE
    if m not in IMAGE_MODELS:
        raise ValueError(f"EMBED_IMAGE_MODEL={m!r}, podporováno {IMAGE_MODELS}")
    return ModelRef(m, MODEL_VERSION[m])


def model_for_index(index: str) -> ModelRef:
    """Aktuálně nastavený model indexu (`text` → text, `image` a `signatures` → obraz)."""
    return text_model() if index in ("text", "wonderfulkb-text") else image_model()


def _invoke(model_id: str, body: dict, bedrock=None) -> dict:
    bedrock = bedrock or clients.bedrock_client()

    def call():
        resp = bedrock.invoke_model(modelId=INVOKE_ID.get(model_id, model_id), body=json.dumps(body),
                                    contentType="application/json", accept="application/json")
        return json.loads(resp["body"].read())

    return clients.call_with_retry(call, limiter=clients.bedrock_limiter)


def _check(vec: list[float], model_id: str) -> list[float]:
    if len(vec) != DIMENSION:
        raise ValueError(f"{model_id} vrátil {len(vec)} dimenzí, index má {DIMENSION}")
    return vec


def _cohere_vectors(out: dict) -> list[list[float]]:
    emb = out["embeddings"]
    return emb["float"] if isinstance(emb, dict) else emb


def _cohere_text_body(texts: list[str], input_type: str) -> dict:
    return {"input_type": input_type, "texts": texts, "embedding_types": ["float"],
            "output_dimension": DIMENSION, "truncate": "NONE"}


def _check_text(text: str) -> None:
    if not text or not text.strip():
        raise ValueError("embed_text: prázdný text")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"embed_text: {len(text)} znaků je nad limitem {MAX_TEXT_CHARS}, použij chunking")


def embed_texts(texts: list[str], *, input_type: str = "search_document", bedrock=None) -> list[list[float]]:
    """Vektory pro víc textů; Cohere je posílá po dávkách, Titan po jednom.

    `input_type` (`search_document` / `search_query`) používá jen Cohere, Titan ho ignoruje.
    """
    for t in texts:
        _check_text(t)
    model = text_model().model
    if model == COHERE_V4:
        vecs: list[list[float]] = []
        for i in range(0, len(texts), COHERE_TEXT_BATCH):
            out = _invoke(model, _cohere_text_body(texts[i:i + COHERE_TEXT_BATCH], input_type), bedrock)
            vecs += [_check(v, model) for v in _cohere_vectors(out)]
        return vecs
    return [_check(_invoke(model, {"inputText": t, "dimensions": DIMENSION, "normalize": True},
                           bedrock)["embedding"], model) for t in texts]


def embed_text(text: str, *, input_type: str = "search_document", bedrock=None) -> list[float]:
    """Vektor (1024) pro text; delší než ~8000 tokenů nejdřív rozděl (chunking).

    Dotazy proti uloženým částem posílej s `input_type="search_query"` (u Cohere to zlepšuje
    hledání, u Titanu nemá význam).
    """
    return embed_texts([text], input_type=input_type, bedrock=bedrock)[0]


def prepare_png(png_bytes: bytes) -> bytes:
    """Do hranic Titanu (strany 128 až 1024 px, bez průhlednosti); malé výřezy se zvětší."""
    img = Image.open(io.BytesIO(png_bytes))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img, mask=img.getchannel("A"))
        img = bg
    else:
        img = img.convert("RGB")
    longest, shortest = max(img.size), min(img.size)
    scale = 1.0
    if longest > IMAGE_MAX_SIDE:
        scale = IMAGE_MAX_SIDE / longest
    if shortest * scale < IMAGE_MIN_SIDE:
        scale = IMAGE_MIN_SIDE / shortest
    if scale != 1.0:
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                         Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def embed_image(png_bytes: bytes, *, bedrock=None) -> list[float]:
    """Vektor (1024) pro obrázek (stránka nebo výřez podpisu) v PNG."""
    if not png_bytes:
        raise ValueError("embed_image: prázdný obrázek")
    model = image_model().model
    b64 = base64.b64encode(prepare_png(png_bytes)).decode()
    if model == COHERE_V4:
        body = {"input_type": "image", "images": [f"data:image/png;base64,{b64}"],
                "embedding_types": ["float"], "output_dimension": DIMENSION}
        return _check(_cohere_vectors(_invoke(model, body, bedrock))[0], model)
    body = {"inputImage": b64, "embeddingConfig": {"outputEmbeddingLength": DIMENSION}}
    return _check(_invoke(model, body, bedrock)["embedding"], model)
