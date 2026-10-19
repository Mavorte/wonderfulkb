import io
import json

import boto3
import httpx
import pytest
from PIL import Image

from pipeline import Settings
from pipeline.vision import MantleVision, RateLimiter, VisionError, clean_text, prepare_image

PNG = io.BytesIO()
Image.new("RGB", (40, 40), "white").save(PNG, format="PNG")


class Creds:
    def get_credentials(self):
        return boto3.Session(aws_access_key_id="AKIATEST", aws_secret_access_key="secret", aws_session_token="tok").get_credentials()


def client(handler, rpm=0):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return MantleVision(Settings(bedrock_rpm=rpm), session=Creds(), http=http, sleep=lambda s: None)


def ok(text, finish="stop"):
    return httpx.Response(200, json={"choices": [{"finish_reason": finish, "message": {"content": text}}]})


def test_request_is_signed_for_mantle_and_carries_the_image():
    seen = []

    def handler(request):
        seen.append(request)
        return ok("Text stránky")

    assert client(handler).transcribe(PNG.getvalue()) == "Text stránky"
    request = seen[0]
    assert str(request.url) == "https://bedrock-mantle.eu-central-1.api.aws/v1/chat/completions"
    auth = request.headers["authorization"]
    assert "AWS4-HMAC-SHA256" in auth and "/eu-central-1/bedrock-mantle/aws4_request" in auth
    assert request.headers["x-amz-security-token"] == "tok"
    body = json.loads(request.content)
    assert body["model"] == "qwen.qwen3-vl-235b-a22b-instruct" and body["temperature"] == 0
    assert body["messages"][1]["content"][0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_throttling_is_retried_then_succeeds():
    answers = [httpx.Response(429), httpx.Response(503), ok("ok")]
    vision = client(lambda request: answers.pop(0))
    assert vision.transcribe(PNG.getvalue()) == "ok" and vision.calls == 3


def test_retries_are_bounded():
    vision = client(lambda request: httpx.Response(429))
    with pytest.raises(VisionError) as error:
        vision.transcribe(PNG.getvalue())
    assert error.value.code == "BEDROCK_HTTP_429" and vision.calls == MantleVision.retries


def test_client_errors_are_not_retried():
    vision = client(lambda request: httpx.Response(403))
    with pytest.raises(VisionError):
        vision.transcribe(PNG.getvalue())
    assert vision.calls == 1


def test_truncated_output_is_not_a_transcript():
    with pytest.raises(VisionError) as error:
        client(lambda request: ok("half", finish="length")).transcribe(PNG.getvalue())
    assert error.value.code == "MODEL_OUTPUT_INCOMPLETE"


def test_clean_text_strips_fence_and_form_feed():
    assert clean_text("```text\nA\fB\n```") == "A B"


def test_large_png_is_shrunk_to_jpeg():
    import os
    noise = Image.frombytes("RGB", (1500, 1500), os.urandom(1500 * 1500 * 3))
    out = io.BytesIO()
    noise.save(out, format="PNG")
    body, fmt = prepare_image(out.getvalue())
    assert fmt == "jpeg" and len(body) <= 2_000_000


def test_rate_limiter_spaces_calls(monkeypatch):
    sleeps, clock = [], [100.0]
    monkeypatch.setattr("pipeline.vision.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("pipeline.vision.time.sleep", sleeps.append)
    limiter = RateLimiter(30)  # one call per 2 s
    for _ in range(3):
        limiter.wait()
    assert sleeps == [pytest.approx(2.0), pytest.approx(4.0)]


def test_split_label_reply():
    from pipeline.vision import LABEL_DELIMITER, split_label_reply
    raw = f'Text strany\n{LABEL_DELIMITER}\n```json\n{{"label": "jine", "description": "d", "confidence": 0.5}}\n```'
    assert split_label_reply(raw) == ("Text strany", {"label": "jine", "description": "d", "confidence": 0.5})
    assert split_label_reply('A\n===\nŠTÍTEK ===\n{"label": "x"}') == ("A", {"label": "x"})
    assert split_label_reply('A\n===\nŠTÍTEK\n{"label": "x"}') == ("A", {"label": "x"})
    assert split_label_reply('ŠTÍTEK na stroji\nB') == ("ŠTÍTEK na stroji\nB", None)
    assert split_label_reply("jen text") == ("jen text", None)
    assert split_label_reply(f"Text\n{LABEL_DELIMITER}\n{{rozbité")[1] is None
    assert split_label_reply(f'Text\n{LABEL_DELIMITER}\n{{"x": 1}}') == ("Text", None)


def test_label_request_goes_into_the_same_call():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return ok("Text")

    schema = {"type": "object", "properties": {"label": {}}}
    client(handler).transcribe(PNG.getvalue(), label={"section": "SEKCE", "schema": schema, "pages": 3, "context": "předchozí"})
    prompt = seen[0]["messages"][1]["content"][1]["text"]
    assert "=== ŠTÍTEK ===" in prompt and "SEKCE" in prompt and "Dokument má 3 stran" in prompt and "předchozí" in prompt
    assert json.dumps(schema, ensure_ascii=False) in prompt and len(seen) == 1
