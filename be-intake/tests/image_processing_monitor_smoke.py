"""Run with the installed intake image as UID10001, without network/provider I/O.

This is artifact verification, not a live AWS/producer claim. The only fakes
are boto provider clients; authorization, membership, AuditStore and ASGI run.
"""

import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
from unittest.mock import MagicMock

import boto3


async def request(app, path, token=None, query=b""):
    headers = [(b"authorization", ("Bearer " + token).encode())] if token else []
    messages = []
    delivered = False
    finished = asyncio.Event()

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await finished.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body", False):
            finished.set()

    await app({"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
               "http_version": "1.1", "method": "GET", "scheme": "http",
               "path": path, "raw_path": path.encode(), "query_string": query,
               "headers": headers, "server": ("localhost", 8080), "client": ("127.0.0.1", 1234),
               "root_path": ""}, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    assert dict(start["headers"])[b"cache-control"] == b"private, no-store"
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start["status"], json.loads(body)


async def main():
    assert os.getuid() == 10001
    sys.path.insert(0, "/app")
    token = "synthetic-artifact-only-credential-0123456789abcdef"
    arn = "arn:aws:secretsmanager:eu-central-1:123456789012:secret:synthetic-image"
    os.environ.update(API_KEY="synthetic-upload", RAW_BUCKET="synthetic-raw", CASES_TABLE="synthetic-cases",
                      DOCS_TABLE="synthetic-docs", HASHES_TABLE="synthetic-hashes", AUDIT_TABLE_NAME="synthetic-audit",
                      PROCESSING_MONITOR_AUTHORIZATION_SECRET_ARN=arn, MONITOR_AUTH_SECRET_ARN="")
    resource, secrets, docs, table = (MagicMock() for _ in range(4))
    resource.Table.side_effect = lambda name: docs if name == "synthetic-docs" else table
    policy = {"version": 1, "credentials": [{"sha256": hashlib.sha256(token.encode()).hexdigest(), "principal_id": "image-test"}],
              "principals": [{"id": "image-test", "type": "SERVICE", "enabled": True, "case_ids": ["case-test"]}],
              "retained_documents": []}
    secrets.get_secret_value.side_effect = lambda **kw: {"SecretString": json.dumps(policy)}
    docs.get_item.return_value = {"Item": {"case_id": "case-test", "document_id": "doc-test"}}
    event = {"schema_version": 1, "event_id": "received-image", "sequence": 0,
             "case_id": "case-test", "document_id": "doc-test", "type": "FileReceived",
             "occurred_at": "2026-10-20T10:00:00Z", "filename": "excluded.pdf"}
    table.query.return_value = {"Items": [event]}
    boto3.resource = lambda *a, **kw: resource
    boto3.client = lambda service, **kw: secrets if service == "secretsmanager" else MagicMock()
    import main as intake
    from document_processing.audit.audit_storage import AuditStore
    import document_processing.audit as audit
    assert isinstance(intake.app.state.processing_monitor_audit_store, AuditStore)
    assert any(route.path.endswith("/{document_id}/events") for route in intake.app.routes)
    path = "/v1/cases/case-test/processing/documents/doc-test/events"
    status, body = await request(intake.app, path, token)
    assert status == 200 and body["coverage"] == "partial"
    assert body["items"][0]["event_id"] == "received-image"
    assert "filename" not in body["items"][0] and "schema_version" not in body["items"][0]
    table.query.assert_called_once()
    docs.get_item.assert_called_once_with(Key={"case_id": "case-test", "document_id": "doc-test"}, ConsistentRead=True)
    assert (await request(intake.app, path))[0] == 403
    assert (await request(intake.app, path, "forged"))[0] == 403
    assert table.query.call_count == 1
    assert (await request(intake.app, path, token, b"next_token=bad"))[0] == 400
    assert table.query.call_count == 1
    policy["principals"][0]["case_ids"] = []
    assert (await request(intake.app, path, token))[0] == 403
    assert table.query.call_count == 1
    policy["principals"][0]["case_ids"] = ["case-test"]
    table.query.side_effect = ValueError("stored decoder failure")
    assert (await request(intake.app, path, token))[0] == 503
    table.query.side_effect = None
    table.query.return_value = {"Items": [{**event, "type": "PageCacheReused", "run_id": "run-test",
        "attempt_no": 1, "stage": "page_transcription", "page_number": 1,
        "cached_status": "completed", "artifact_ids": ["internal-reference"]}]}
    status, body = await request(intake.app, path, token)
    assert status == 200 and body["items"][0]["cached_status"] == "completed"
    assert body["items"][0]["artifact_ids"] == ["internal-reference"]
    table.query.return_value = {"Items": [{**event, "event_id": "pages-image-terminal", "sequence": 7,
        "type": "PageCompleted", "run_id": "run-test", "attempt_no": 1,
        "stage": "page_transcription", "page_number": 1, "method": "native", "duration_ms": 12.5}]}
    pages_path = path.removesuffix("/events") + "/runs/run-test/pages"
    status, body = await request(intake.app, pages_path, token, b"attempt_no=1&limit=1")
    assert status == 200 and body["coverage"] == "partial" and body["observed_at"]
    expected = {"event_id": "pages-image-terminal", "sequence": 7, "type": "PageCompleted",
        "occurred_at": event["occurred_at"], "run_id": "run-test", "attempt_no": 1,
        "stage": "page_transcription", "page_number": 1, "method": "native", "duration_ms": 12.5}
    assert body["items"] == [expected] and body["next_token"] is None
    status, body = await request(intake.app, pages_path.removesuffix("/pages") + "/steps", token, b"attempt_no=1")
    assert status == 200 and body["items"] == [expected]
    from urllib.parse import urlencode
    from document_processing.audit.audit_queries import document_key
    run_path = path.removesuffix("/events") + "/runs/run-test/events"
    # Exercise the installed pages router itself, not just the event projection.
    assert "/site-packages/" in audit.__file__
    for cached_status in ("completed", "failed"):
        cached = {**event, "event_id": "cache-pages-" + cached_status, "sequence": 9,
                  "type": "PageCacheReused", "run_id": "run-test", "attempt_no": 1,
                  "stage": "page_transcription", "page_number": 2,
                  "cached_status": cached_status, "cached_method": "vision",
                  "artifact_ids": ["opaque-cache-result"]}
        if cached_status == "completed":
            cached["cached_model"] = "stored-model"
        table.query.return_value = {"Items": [{**cached, "s3_key": "excluded", "page": {"text": "excluded"}}]}
        expected_cache = {k: v for k, v in cached.items()
                           if k not in {"schema_version", "case_id", "document_id", "filename"}}
        before = table.query.call_count
        status, body = await request(intake.app, pages_path, token, b"attempt_no=1&limit=1")
        assert status == 200 and body["items"] == [expected_cache]
        assert body["coverage"] == "partial" and body["observed_at"] and body["next_token"] is None
        assert table.query.call_count == before + 1 and table.query.call_args.kwargs["Limit"] == 1
        for event_path in (path, run_path):
            status, body = await request(intake.app, event_path, token)
            assert status == 200
            assert body["items"] == [{**expected_cache, "case_id": "case-test", "document_id": "doc-test"}]
        status, body = await request(intake.app, pages_path.removesuffix("/pages") + "/steps", token, b"attempt_no=1")
        assert status == 200 and body["items"] == []
        assert (await request(intake.app, pages_path, token, b"attempt_no=2"))[1]["items"] == []
        assert (await request(intake.app, pages_path.replace("run-test", "other-run"), token,
                              b"attempt_no=1"))[1]["items"] == []
    key = {"pk": document_key("case-test", "doc-test"), "sk": "EVENT#other"}
    table.query.side_effect = [
        {"Items": [event, {**event, "event_id": "other", "type": "RunQueued", "run_id": "other-run"}], "LastEvaluatedKey": key},
        {"Items": [{**event, "event_id": "wanted", "type": "RunQueued", "run_id": "run-test"}]},
    ]
    before = table.query.call_count
    status, body = await request(intake.app, run_path, token, b"limit=2")
    assert status == 200 and body["items"] == [] and body["next_token"]
    cursor = body["next_token"]
    assert table.query.call_count == before + 1
    status, body = await request(intake.app, run_path, token, urlencode({"next_token": cursor, "limit": 2}).encode())
    assert status == 200 and body["items"][0]["event_id"] == "wanted" and body["next_token"] is None
    assert table.query.call_args.kwargs["ExclusiveStartKey"] == key
    assert (await request(intake.app, run_path.replace("run-test", "other-run"), token,
                          urlencode({"next_token": cursor}).encode()))[0] == 400
    assert table.query.call_count == before + 2
    table.query.side_effect = None
    table.query.return_value = {"Items": [{**event, "event_id": "extraction-image-terminal", "sequence": 8,
        "type": "StepFailed", "run_id": "run-test", "attempt_no": 1, "stage": "extraction",
        "duration_ms": 2.5, "error_code": "EXTRACTION_FAILED", "fields": "excluded"}]}
    expected = {"event_id": "extraction-image-terminal", "sequence": 8, "type": "StepFailed",
        "occurred_at": event["occurred_at"], "run_id": "run-test", "attempt_no": 1,
        "stage": "extraction", "duration_ms": 2.5, "error_code": "EXTRACTION_FAILED"}
    status, body = await request(intake.app, pages_path.removesuffix("/pages") + "/steps", token, b"attempt_no=1")
    assert status == 200 and body["items"] == [expected] and body["coverage"] == "partial"
    for event_path in (path, run_path):
        status, body = await request(intake.app, event_path, token)
        assert status == 200
        assert body["items"] == [{**expected, "case_id": "case-test", "document_id": "doc-test"}]
    assert (await request(intake.app, pages_path, token, b"attempt_no=1"))[1]["items"] == []
    table.scan.assert_not_called()
    audit_root = Path(audit.__file__).parent
    hashes = {str(path.relative_to(audit_root)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(audit_root.rglob("*.py"))}
    source = {name: hashlib.sha256(Path("/app", name).read_bytes()).hexdigest() for name in (
        "main.py", "processing_monitor_authorization.py", "processing_monitor_routes.py",
        "processing_monitor_lifecycle_routes.py", "processing_monitor_page_routes.py",
        "processing_monitor_step_routes.py", "content_hashes.py")}
    print(json.dumps({"uid": os.getuid(), "package_version": importlib.metadata.version("wonderfulkb-document-processing"),
                      "audit_source_hashes": hashes, "intake_source_hashes": source,
                      "assertions": "ASGI200/private-no-store/FileReceived+cacheDTO+nonempty-pages+single-step-terminal/cache-pages-completed-failed-unknown-model-document-run-parity-steps-exclusion-run-attempt-isolation/extraction-failure-duration-document-run-parity-pages-exclusion/run-events-empty-continuation-filter-cross-run400/grant403/cursor400/read503; provider I/O stubbed"}, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
