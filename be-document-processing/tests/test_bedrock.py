import json

import boto3
import httpx
import pytest

from document_processing.bedrock import BedrockClient, BedrockOcr, parse_json_response
from document_processing.config import Settings
from document_processing.providers import ProviderError
from conftest import make_pdf
import pymupdf


def session():
    return boto3.Session(aws_access_key_id="offline-test", aws_secret_access_key="offline-test",
                         aws_session_token="temporary-test-token", region_name="eu-central-1")


def test_mantle_is_signed_for_frankfurt_with_temporary_credentials():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]})
    client = BedrockClient(Settings(), session=session(), http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.complete("qwen.qwen3-vl-235b-a22b-instruct", "system", "prompt") == "{}"
    request = requests[0]
    assert request.url.host == "bedrock-mantle.eu-central-1.api.aws"
    assert request.url.path == "/v1/chat/completions"
    assert "/eu-central-1/bedrock-mantle/aws4_request" in request.headers["authorization"]
    assert request.headers["x-amz-security-token"] == "temporary-test-token"
    assert json.loads(request.content)["model"] == "qwen.qwen3-vl-235b-a22b-instruct"


def test_gemma_uses_its_own_mantle_route():
    urls = []
    def handler(request):
        urls.append(str(request.url))
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]})
    client = BedrockClient(Settings(), session=session(), http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    client.complete("google.gemma-4-31b", "system", "prompt")
    assert urls == ["https://bedrock-mantle.eu-central-1.api.aws/openai/v1/chat/completions"]


def test_region_cannot_fall_back_outside_frankfurt():
    with pytest.raises(ValueError, match="Frankfurt"):
        Settings(bedrock_region="eu-west-1")


def test_qwen_converse_is_rejected_in_frankfurt():
    client = BedrockClient(Settings(bedrock_api="converse"), session=session())
    with pytest.raises(ProviderError, match="QWEN_FRANKFURT_REQUIRES_MANTLE"):
        client.complete("qwen.qwen3-vl-235b-a22b", "system", "prompt")


def test_truncated_output_is_not_a_successful_transcription():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]})
    client = BedrockClient(Settings(), session=session(), http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ProviderError, match="MODEL_OUTPUT_INCOMPLETE"):
        client.complete("qwen.qwen3-vl-235b-a22b-instruct", "system", "prompt")


def test_bedrock_ocr_receives_pixels_without_hidden_pdf_text():
    class Client:
        def complete(self, model, system, prompt, image=None):
            assert image.startswith(b"\x89PNG")
            assert "expected_ico" not in prompt
            return json.dumps({"blocks": [{"type": "paragraph", "text": "ICO 98007009"}], "tables": [], "warnings": []})
    with pymupdf.open(stream=make_pdf("ICO 98007009"), filetype="pdf") as pdf:
        result = BedrockOcr(Settings(), Client()).transcribe(pdf[0], 1, "auto")
    assert result.method == "vision"
    assert result.blocks[0].bbox is None
    assert result.blocks[0].confidence is None


def test_json_parser_rejects_surrounding_unstructured_answers():
    assert parse_json_response('```json\n{"value": 1}\n```') == {"value": 1}
    with pytest.raises(ValueError):
        parse_json_response('I think: {"value": 1}')
