"""Case status from this side: intake_in_progress on a new document, evaluating after the Wonderful webhook."""
import json
import urllib.error

import boto3
import pytest

from trigger import case_step, common, enqueue_handler, wonderful_webhook

from .conftest import CASE, stream_record


def put_case(ctx, status="open", case_id=CASE):
    ctx.cases.put_item(Item={"case_id": case_id, "client_id": "c", "status": status,
                             "created_at": "2026-10-20T08:00:00.000000Z"})


def status(ctx, case_id=CASE):
    return ctx.get_case(case_id)["status"]


@pytest.fixture
def webhook(monkeypatch):
    calls = []
    monkeypatch.setenv("WONDERFUL_WEBHOOK_SECRET", "wonderfulkb/wonderful-webhook")
    monkeypatch.setattr(wonderful_webhook, "start_evaluation", lambda case_id: calls.append(case_id) or 200)
    return calls


@pytest.mark.parametrize("before, after", [("open", "intake_in_progress"),
                                           ("awaiting_clarification", "intake_in_progress"),
                                           ("evaluating", "evaluating"), ("awaiting_decision", "awaiting_decision"),
                                           ("completed", "completed")])
def test_new_document_starts_intake(ctx, monkeypatch, before, after):
    monkeypatch.setattr(enqueue_handler, "_ctx", ctx)
    put_case(ctx, before)
    assert enqueue_handler.handler({"Records": [stream_record(CASE, "d1")]}) == {"batchItemFailures": []}
    assert status(ctx) == after
    assert ctx.get_case(CASE).get("status_updated_at") if before != after else True


def test_case_status_failure_does_not_hold_the_document(ctx, monkeypatch):
    monkeypatch.setattr(enqueue_handler, "_ctx", ctx)
    ctx.cases_name = "no-such-table"
    assert enqueue_handler.handler({"Records": [stream_record("OTHER", "d1")]}) == {"batchItemFailures": []}
    assert ctx.get_row("OTHER", "d1")["processing_status"] == "queued"


def test_processed_case_calls_the_webhook_once_and_moves_to_evaluating(ctx, webhook):
    put_case(ctx, "intake_in_progress")
    assert case_step.start_evaluation(ctx, CASE) == "started"
    assert status(ctx) == "evaluating"
    assert case_step.start_evaluation(ctx, CASE) == "skipped (evaluating)"  # a repeated case message
    assert webhook == [CASE]


def test_failed_webhook_keeps_the_status_for_the_retry(ctx, monkeypatch):
    monkeypatch.setenv("WONDERFUL_WEBHOOK_SECRET", "x")

    def down(case_id):
        raise wonderful_webhook.WebhookError("webhook answered 503")
    monkeypatch.setattr(wonderful_webhook, "start_evaluation", down)
    put_case(ctx, "intake_in_progress")
    with pytest.raises(wonderful_webhook.WebhookError):
        case_step.start_evaluation(ctx, CASE)
    assert status(ctx) == "intake_in_progress"


def test_disabled_webhook_and_unknown_case_change_nothing(ctx, monkeypatch):
    monkeypatch.delenv("WONDERFUL_WEBHOOK_SECRET", raising=False)
    put_case(ctx, "intake_in_progress")
    assert case_step.start_evaluation(ctx, CASE) == "webhook_disabled"
    assert status(ctx) == "intake_in_progress"
    assert case_step.start_evaluation(ctx, "UNKNOWN") == "no_case"


def test_copy_check_failure_still_starts_the_evaluation(ctx, webhook, monkeypatch):
    from pipeline import copies

    def broken(case_id, options):
        raise RuntimeError("S3 down")
    monkeypatch.setattr(copies, "copy_case", broken)
    put_case(ctx, "intake_in_progress")
    with pytest.raises(RuntimeError, match="S3 down"):
        case_step.run(CASE, None, ctx)
    assert webhook == [CASE] and status(ctx) == "evaluating"
    monkeypatch.setattr(copies, "copy_case", lambda case_id, options: {"case_id": case_id})
    assert case_step.run(CASE, None, ctx)["evaluation"] == "skipped (evaluating)"  # the retry
    assert webhook == [CASE]


class _Response:
    status = 202

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _secret(ctx, monkeypatch, value):
    monkeypatch.setattr(wonderful_webhook, "_config", None)
    boto3.client("secretsmanager", region_name="eu-central-1").create_secret(Name="wh", SecretString=json.dumps(value))
    monkeypatch.setenv("WONDERFUL_WEBHOOK_SECRET", "wh")


def test_webhook_request(ctx, monkeypatch):
    _secret(ctx, monkeypatch, {"url": "https://example.invalid/hook/abc", "secret": "s3cr3t"})
    sent = []
    monkeypatch.setattr(wonderful_webhook.urllib.request, "urlopen", lambda request, timeout: sent.append(request) or _Response())
    assert wonderful_webhook.start_evaluation(CASE) == 202
    request = sent[0]
    assert (request.full_url, request.get_method()) == ("https://example.invalid/hook/abc", "POST")
    assert request.get_header("X-webhook-secret") == "s3cr3t"
    assert request.get_header("Content-type") == "application/json"
    assert json.loads(request.data) == {"payload": {"case_id": CASE}}


def test_webhook_errors(ctx, monkeypatch):
    _secret(ctx, monkeypatch, {"url": "https://example.invalid/hook/abc", "secret": "s3cr3t"})

    def http_error(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)
    monkeypatch.setattr(wonderful_webhook.urllib.request, "urlopen", http_error)
    with pytest.raises(wonderful_webhook.WebhookError, match="401"):
        wonderful_webhook.start_evaluation(CASE)

    def unreachable(request, timeout):
        raise urllib.error.URLError("timed out")
    monkeypatch.setattr(wonderful_webhook.urllib.request, "urlopen", unreachable)
    with pytest.raises(wonderful_webhook.WebhookError, match="unreachable"):
        wonderful_webhook.start_evaluation(CASE)


def test_webhook_secret_must_be_complete(ctx, monkeypatch):
    _secret(ctx, monkeypatch, {"url": "http://plain.invalid", "secret": "x"})
    with pytest.raises(wonderful_webhook.WebhookError):
        wonderful_webhook.start_evaluation(CASE)
