from pathlib import Path

import yaml
from jsonschema import Draft7Validator
from openapi_spec_validator import validate_spec


CONTRACT = Path(__file__).parents[1] / "contracts" / "openapi-processing-monitor.yaml"
PREFIX = "/cases/{case_id}/processing/documents/{document_id}"
APPROVED_PATHS = {
    f"{PREFIX}/events",
    f"{PREFIX}/runs/{{run_id}}/events",
    f"{PREFIX}/runs/{{run_id}}/attempts",
    f"{PREFIX}/runs/{{run_id}}/steps",
    f"{PREFIX}/runs/{{run_id}}/pages",
    f"{PREFIX}/runs",
    f"{PREFIX}/runs/{{run_id}}",
    f"{PREFIX}/audit",
}


def _resolve(document, ref):
    assert ref.startswith("#/"), ref
    value = document
    for part in ref[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    return value


def test_source_validation_steps_have_dedicated_exact_fact_schemas():
    document = yaml.safe_load(CONTRACT.read_text())
    operation = document["paths"][f"{PREFIX}/runs/{{run_id}}/steps"]["get"]
    assert operation["security"] == [{"MonitoringServiceBearer": []}]
    branches = document["components"]["schemas"]["StepObservation"]["oneOf"]
    source_branches = [branch for branch in branches if "SourceValidation" in branch["$ref"]]
    assert len(source_branches) == 3
    for branch in source_branches:
        schema = _resolve(document, branch["$ref"])
        assert schema["additionalProperties"] is False
        assert {"event_id", "sequence", "occurred_at", "type", "stage", "run_id", "attempt_no"} <= set(schema["required"])
        assert schema["properties"]["stage"]["enum"] == ["source_validation"]
        assert "page_number" not in schema["properties"]
        assert "duration_ms" not in schema["required"]
        assert not ({"case_id", "document_id", "status", "content"} & set(schema["properties"]))


def test_pages_share_executed_observations_with_steps_but_not_cache_reuse():
    document = yaml.safe_load(CONTRACT.read_text())
    schemas = document["components"]["schemas"]
    branches = schemas["PageObservation"]["oneOf"]
    assert len(branches) == 4
    types = []
    for branch in branches:
        if branch["$ref"].endswith("/PageCacheReusedObservation"):
            assert branch not in schemas["StepObservation"]["oneOf"]
        else:
            assert branch in schemas["StepObservation"]["oneOf"]
        schema = _resolve(document, branch["$ref"])
        assert schema["additionalProperties"] is False
        assert {"event_id", "sequence", "occurred_at", "type", "stage", "run_id", "attempt_no", "page_number"} <= set(schema["required"])
        props = schema["properties"]
        types.extend(props["type"]["enum"])
        assert props["stage"]["enum"] == ["page_transcription"]
        if "duration_ms" in props:
            assert props["duration_ms"] == {"type": "number", "minimum": 0}
            assert "duration_ms" not in schema["required"]
        assert not ({"case_id", "document_id", "status", "content", "blocks", "tables", "text"} & set(props))
    assert types == ["StepStarted", "PageCompleted", "PageFailed", "PageCacheReused"]


def test_only_approved_observation_paths_are_published():
    document = yaml.safe_load(CONTRACT.read_text())
    assert document["openapi"].startswith("3.")
    assert set(document["paths"]) == APPROVED_PATHS
    assert all(set(item) == {"get", "parameters"} for item in document["paths"].values())


def test_all_local_references_resolve_and_responses_are_bounded_private_observations():
    document = yaml.safe_load(CONTRACT.read_text())

    def walk(value):
        if isinstance(value, dict):
            if "$ref" in value:
                assert isinstance(_resolve(document, value["$ref"]), dict)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(document)
    for path, path_item in document["paths"].items():
        operation = path_item["get"]
        params = path_item["parameters"] + operation.get("parameters", [])
        assert any(_resolve(document, p["$ref"])["name"] == "limit" for p in params)
        text = (str(operation) + str(document["info"]["description"])).lower()
        assert "one bounded observation window" in text
        assert "private, no-store" in text
        assert "shared api key" in text
        assert "503" in text
    limit = _resolve(document, "#/components/parameters/Limit")["schema"]
    assert limit["minimum"] == 1 and limit["maximum"] == 100
    assert "operation-bound" in _resolve(document, "#/components/parameters/NextToken")["description"]


def test_observation_schemas_have_allowlisted_fields_and_no_content_projections():
    document = yaml.safe_load(CONTRACT.read_text())
    schemas = document["components"]["schemas"]
    schema = schemas["ObservationCollection"]
    assert set(schema["required"]) == {"items", "next_token", "observed_at", "coverage"}
    event = schemas["ObservationItem"]
    assert "oneOf" in event
    event_types = {_resolve(document, branch["$ref"])["properties"]["type"]["enum"][0]: _resolve(document, branch["$ref"])
                   for branch in event["oneOf"]}
    assert "FileReceived" in event_types
    assert "run_id" not in event_types["FileReceived"]["properties"]
    assert event_types["AttemptStarted"]["properties"]["attempt_no"]["type"] == "integer"
    assert event_types["PageCompleted"]["properties"]["page_number"]["type"] == "integer"
    assert all(_resolve(document, branch["$ref"])["additionalProperties"] is False for branch in event["oneOf"])
    forbidden = {"content", "raw_error", "s3_key", "bucket", "url", "total"}
    for name, schema in schemas.items():
        props = schema.get("properties", {})
        assert not (forbidden & set(props)), (name, forbidden & set(props))
    assert "FileReceived" in str(event)
    text = str(document["paths"]).lower()
    assert "FileReceived has no run scope" in str(document["paths"])
    assert "pagecompleted and pagefailed are the only page terminal" in text
    assert "cache reuse is not a new inference" in text
    assert "publication does not automatically terminate a run" in text
    assert "synthetic" in str(document["paths"]).lower()


def test_partial_empty_continuation_and_lifecycle_scope_are_explicit():
    document = yaml.safe_load(CONTRACT.read_text())
    rendered = str(document).lower()
    assert "partial" in rendered
    assert "empty items" in rendered and "next_token" in rendered
    assert "snapshot" in rendered and "incremental" in rendered
    assert "complete" in rendered and "latest" in rendered
    assert "total" not in document["components"]["schemas"]
    assert "server-authenticated service principal" in rendered
    assert "explicit server-owned" in rendered and "case grant" in rendered
    assert "authorization source failure is fail-closed" in rendered
    assert document["security"] == [{"MonitoringServiceBearer": []}]
    scheme = document["components"]["securitySchemes"]["MonitoringServiceBearer"]
    assert scheme["type"] == "http" and scheme["scheme"] == "bearer"
    schemas = document["components"]["schemas"]
    assert {"RunSummary", "RunDetail", "DocumentAudit"} <= set(schemas)
    assert {"state", "evidence", "attempts", "published_results"} <= set(schemas["RunDetail"]["properties"])
    assert "event_type" in schemas["LifecycleEvidence"]["properties"]
    assert "terminal_state" in schemas["LifecycleAttempt"]["properties"]
    assert {"unknown", "ambiguous", "completed", "partial", "failed"} <= set(
        schemas["RunDetail"]["properties"]["state"]["enum"])
    audit_response = _resolve(document, document["paths"][f"{PREFIX}/audit"]["get"]["responses"]["200"]["$ref"])
    assert "DocumentAudit" in audit_response["content"]["application/json"]["schema"]["$ref"]
    for path_item in document["paths"].values():
        responses = path_item["get"]["responses"]
        assert {"200", "400", "403", "404", "503"} <= set(responses)
        for response_ref in responses.values():
            response = _resolve(document, response_ref["$ref"])
            assert "Cache-Control" in response["headers"]
            assert response["headers"]["Cache-Control"]["$ref"] == "#/components/headers/PrivateCache"


def test_event_schemas_require_exact_scope_status_and_allowlisted_payloads():
    document = yaml.safe_load(CONTRACT.read_text())
    validate_spec(document)
    schemas = document["components"]["schemas"]
    events = {name: schema for name, schema in schemas.items()
              if name in {"FileReceived", "RunQueued", "AttemptStarted", "StepStarted", "StepFinished",
                          "StepFailed", "PageCacheReused", "PageCompleted", "PageFailed", "ResultPublished",
                          "RetryEnqueued", "AttemptFinished", "RunFinished"}}

    expected_required = {
        "FileReceived": {"event_id", "type", "occurred_at"},
        "RunQueued": {"event_id", "type", "occurred_at", "run_id"},
        "AttemptStarted": {"event_id", "type", "occurred_at", "run_id", "attempt_no"},
        "StepStarted": {"event_id", "type", "occurred_at", "run_id", "attempt_no", "stage"},
        "StepFinished": {"event_id", "type", "occurred_at", "run_id", "attempt_no", "stage"},
        "StepFailed": {"event_id", "type", "occurred_at", "run_id", "attempt_no", "stage", "error_code"},
        "PageCacheReused": {"event_id", "type", "occurred_at", "run_id", "attempt_no", "page_number", "stage", "cached_status"},
        "PageCompleted": {"event_id", "type", "occurred_at", "run_id", "attempt_no", "page_number", "stage"},
        "PageFailed": {"event_id", "type", "occurred_at", "run_id", "attempt_no", "page_number", "error_code"},
        "ResultPublished": {"event_id", "type", "occurred_at", "run_id", "attempt_no", "result_status"},
        "RetryEnqueued": {"event_id", "type", "occurred_at", "run_id", "attempt_no"},
        "AttemptFinished": {"event_id", "type", "occurred_at", "run_id", "attempt_no", "attempt_status"},
        "RunFinished": {"event_id", "type", "occurred_at", "run_id", "run_status"},
    }
    assert set(events) == set(expected_required)
    status_values = ["completed", "partial", "failed"]
    for name, required in expected_required.items():
        schema = events[name]
        assert required <= set(schema["required"]), name
        assert schema["additionalProperties"] is False
        assert "outcome" not in schema["properties"]
        for field in required - {"event_id", "type", "occurred_at"}:
            assert field in schema["properties"], (name, field)
        if name in {"AttemptFinished", "RunFinished", "ResultPublished"}:
            field = {"AttemptFinished": "attempt_status", "RunFinished": "run_status",
                     "ResultPublished": "result_status"}[name]
            assert schema["properties"][field]["enum"] == status_values
        if name == "StepFinished":
            assert "duration_ms" in schema["properties"]
        if name in {"StepStarted", "StepFinished", "StepFailed"}:
            assert schema["properties"]["stage"]["enum"] == ["source_validation", "page_transcription", "extraction", "signature_detection", "result_publishing"]
        if name in {"PageCacheReused", "PageCompleted", "PageFailed"}:
            assert schema["properties"]["stage"]["enum"] == ["page_transcription"]
        if name == "RetryEnqueued":
            assert "reason_code" in schema["properties"] and "retry_reason" not in schema["properties"]
        if name in {"StepFailed", "PageFailed"}:
            assert schema["properties"]["error_code"]["type"] == "string"
        if name == "RunFinished":
            assert "attempt_no" not in schema["required"]
        if name == "FileReceived":
            assert "run_id" not in schema["properties"]

    base = {"event_id": "evt-1", "occurred_at": "2026-10-20T12:00:00Z"}
    attempt = events["AttemptFinished"]
    attempt_validator = Draft7Validator(attempt)
    valid_attempt = {**base, "type": "AttemptFinished", "run_id": "run-1", "attempt_no": 1,
                     "attempt_status": "partial"}
    assert attempt_validator.is_valid(valid_attempt)
    assert not attempt_validator.is_valid({**valid_attempt, "attempt_status": "unknown"})
    assert not attempt_validator.is_valid({k: v for k, v in valid_attempt.items() if k != "attempt_no"})
    assert not attempt_validator.is_valid({**valid_attempt, "secret": "no"})

    run_validator = Draft7Validator(events["RunFinished"])
    valid_run = {**base, "type": "RunFinished", "run_id": "run-1", "run_status": "completed"}
    assert run_validator.is_valid(valid_run)
    assert not run_validator.is_valid({k: v for k, v in valid_run.items() if k != "run_id"})
    assert not run_validator.is_valid({**valid_run, "run_status": "queued"})
    assert not run_validator.is_valid({**valid_run, "attempt_no": "1"})
    file_received = {**base, "type": "FileReceived"}
    assert Draft7Validator(events["FileReceived"]).is_valid(file_received)
    assert not Draft7Validator(events["FileReceived"]).is_valid({**file_received, "run_id": "run-1"})
