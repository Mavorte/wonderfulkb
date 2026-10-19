import base64
import io

import pytest
from botocore.exceptions import ClientError
from PIL import Image

from embed import clients, embed_image, embed_text
from embed.embeddings import prepare_png
from conftest import FakeBedrock, png


def test_embed_text_request_and_result(bedrock):
    vec = embed_text("Smlouva o úvěru", bedrock=bedrock)
    model, body = bedrock.calls[0]
    assert model == "amazon.titan-embed-text-v2:0"
    assert body == {"inputText": "Smlouva o úvěru", "dimensions": 1024, "normalize": True}
    assert len(vec) == 1024


def test_embed_text_rejects_empty_and_too_long(bedrock):
    with pytest.raises(ValueError):
        embed_text("   ", bedrock=bedrock)
    with pytest.raises(ValueError):
        embed_text("a" * 50_001, bedrock=bedrock)
    assert bedrock.calls == []


def test_embed_image_request(bedrock):
    embed_image(png(), bedrock=bedrock)
    model, body = bedrock.calls[0]
    assert model == "amazon.titan-embed-image-v1"
    assert body["embeddingConfig"] == {"outputEmbeddingLength": 1024}
    Image.open(io.BytesIO(base64.b64decode(body["inputImage"]))).verify()


def test_prepare_png_bounds_and_alpha():
    big = Image.open(io.BytesIO(prepare_png(png(3000, 2000))))
    assert max(big.size) == 1024
    tiny = Image.open(io.BytesIO(prepare_png(png(60, 30))))
    assert min(tiny.size) >= 128
    buf = io.BytesIO()
    Image.new("RGBA", (200, 200), (0, 0, 0, 0)).save(buf, "PNG")
    out = Image.open(io.BytesIO(prepare_png(buf.getvalue())))
    assert out.mode == "RGB" and out.getpixel((5, 5)) == (255, 255, 255)


def test_retry_on_throttling_then_success():
    b = FakeBedrock(fail_first=2)
    assert len(embed_text("ahoj", bedrock=b)) == 1024
    assert len(b.calls) == 1


def test_retry_gives_up_and_non_retryable_not_retried():
    b = FakeBedrock(fail_first=99)
    with pytest.raises(ClientError):
        embed_text("ahoj", bedrock=b)
    assert b.fail_first == 99 - 6

    class Bad:
        n = 0

        def invoke_model(self, **kw):
            Bad.n += 1
            raise ClientError({"Error": {"Code": "ValidationException", "Message": "x"},
                               "ResponseMetadata": {"HTTPStatusCode": 400}}, "InvokeModel")

    with pytest.raises(ClientError):
        embed_text("ahoj", bedrock=Bad())
    assert Bad.n == 1


def test_wrong_dimension_is_error():
    class Short:
        def invoke_model(self, **kw):
            import json
            return {"body": io.BytesIO(json.dumps({"embedding": [0.1] * 10}).encode())}

    with pytest.raises(ValueError):
        embed_text("ahoj", bedrock=Short())


def test_rate_limiter_waits_when_window_full():
    t = [0.0]
    slept = []

    def sleep(s):
        slept.append(s)
        t[0] += s

    rl = clients.RateLimiter(limit=2, window=60, clock=lambda: t[0], sleep=sleep)
    for _ in range(3):
        rl.wait()
    assert len(slept) == 1 and 59 <= slept[0] <= 60.1


def test_cohere_text_via_config(bedrock, monkeypatch):
    from embed.embeddings import embed_texts
    monkeypatch.setenv("EMBED_TEXT_MODEL", "cohere.embed-v4:0")
    vecs = embed_texts(["a", "b", "c"], input_type="search_query", bedrock=bedrock)
    assert len(vecs) == 3 and all(len(v) == 1024 for v in vecs)
    model, body = bedrock.calls[0]
    assert model == "eu.cohere.embed-v4:0"  # inference profil, ne holé ID
    assert body["input_type"] == "search_query" and body["output_dimension"] == 1024
    assert body["texts"] == ["a", "b", "c"] and body["embedding_types"] == ["float"]
    assert len(bedrock.calls) == 1  # jedna dávka


def test_cohere_text_batches(bedrock, monkeypatch):
    from embed.embeddings import COHERE_TEXT_BATCH, embed_texts
    monkeypatch.setenv("EMBED_TEXT_MODEL", "cohere.embed-v4:0")
    assert len(embed_texts(["x"] * (COHERE_TEXT_BATCH + 1), bedrock=bedrock)) == COHERE_TEXT_BATCH + 1
    assert len(bedrock.calls) == 2


def test_cohere_image_via_config(bedrock, monkeypatch):
    monkeypatch.setenv("EMBED_IMAGE_MODEL", "cohere.embed-v4:0")
    assert len(embed_image(png(), bedrock=bedrock)) == 1024
    model, body = bedrock.calls[0]
    assert model == "eu.cohere.embed-v4:0" and body["input_type"] == "image"
    assert body["images"][0].startswith("data:image/png;base64,") and body["output_dimension"] == 1024


def test_unknown_model_rejected(monkeypatch):
    monkeypatch.setenv("EMBED_TEXT_MODEL", "nejaky.model")
    with pytest.raises(ValueError):
        embed_text("a")
