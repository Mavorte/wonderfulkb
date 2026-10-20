import pytest
from copy import deepcopy

from document_processing.audit.audit_page_observations import to_page_observations


def envelope(event_type, **extra):
    return {
        "event_id": "evt-1", "type": event_type, "sequence": 3,
        "occurred_at": "2026-10-20T12:00:00Z", "run_id": "run-1",
        "attempt_no": 1, "page_number": 2, **extra,
    }


def test_completed_mapping_is_content_free_and_does_not_mutate_input():
    event = envelope("PageCompleted", stage="page_transcription", duration_ms=12,
                     method="native", model="model-a", text="secret", url="secret")
    original = dict(event)
    result = to_page_observations([event], run_id="run-1", attempt_no=1)
    assert result == [{key: value for key, value in event.items() if key in {
        "event_id", "type", "sequence", "occurred_at", "run_id", "attempt_no",
        "page_number", "stage", "duration_ms", "method", "model",
    }}]
    assert result[0] is not event
    assert event == original


@pytest.mark.parametrize("event_type,fields", [
    ("PageCompleted", {"stage": "page_transcription", "duration_ms": 9, "method": "native", "model": "m"}),
    ("PageFailed", {"stage": "page_transcription", "error_code": "OCR_FAILED"}),
    ("PageCacheReused", {"cached_status": "completed", "cached_method": "vision",
                          "cached_model": "m", "artifact_ids": ["opaque-1"],
                          "stage": "page_transcription"}),
    ("StepStarted", {"stage": "page_transcription"}),
])
def test_event_type_allowlists(event_type, fields):
    event = envelope(event_type, **fields, text="private", exception="private")
    assert to_page_observations([event], run_id="run-1", attempt_no=1) == [
        {key: value for key, value in event.items() if key in {
            "event_id", "type", "sequence", "occurred_at", "run_id", "attempt_no",
            "page_number", "stage", "duration_ms", "method", "model", "error_code",
            "cached_status", "cached_method", "cached_model", "artifact_ids",
        }}
    ]


def test_filters_scope_and_unknown_events_preserving_observed_order_and_fragments():
    events = [
        envelope("PageFailed", stage="page_transcription", error_code="E"),
        {**envelope("PageCompleted", stage="page_transcription"), "page_number": 4},
        {**envelope("PageCompleted", stage="page_transcription"), "run_id": "other"},
        envelope("Unrecognized", stage="page_transcription"),
        envelope("StepStarted", stage="unknown"),
    ]
    result = to_page_observations(events, run_id="run-1", attempt_no=1)
    assert [item["type"] for item in result] == ["PageFailed", "PageCompleted"]
    assert [item["page_number"] for item in result] == [2, 4]


def test_malformed_scope_is_rejected():
    with pytest.raises((TypeError, ValueError)):
        to_page_observations([envelope("PageCompleted", stage="page_transcription")],
                             run_id="run-1", attempt_no=0)
    with pytest.raises((TypeError, ValueError)):
        to_page_observations([{"type": "PageCompleted"}], run_id="run-1", attempt_no=1)


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_cache_reuse_preserves_cached_outcome_without_inference(status):
    event = envelope("PageCacheReused", stage="page_transcription", cached_status=status,
                     cached_method="unknown", cached_model="unknown", text="private",
                     bucket="private", url="private")
    expected = {key: value for key, value in event.items() if key in {
        "event_id", "type", "sequence", "occurred_at", "run_id", "attempt_no",
        "page_number", "stage", "cached_status", "cached_method", "cached_model",
    }}
    assert to_page_observations([event], run_id="run-1", attempt_no=1) == [expected]


def test_terminal_only_and_repeated_page_observations_remain_distinct():
    first = envelope("PageCompleted", stage="page_transcription", duration_ms=12)
    second = {**first, "event_id": "evt-2", "sequence": 4, "duration_ms": 15}
    terminal_only = envelope("PageFailed", stage="page_transcription", error_code="OCR_FAILED")
    result = to_page_observations([first, second, terminal_only], run_id="run-1", attempt_no=1)
    assert [item["event_id"] for item in result] == ["evt-1", "evt-2", "evt-1"]
    assert [item["type"] for item in result] == ["PageCompleted", "PageCompleted", "PageFailed"]
    assert all(item["type"] != "StepFinished" for item in result)


def test_scope_filter_covers_attempt_and_run_and_input_is_deeply_immutable():
    selected = envelope("PageCacheReused", stage="page_transcription",
                        cached_status="failed", artifact_ids=["opaque-id"], secret={"x": [1]})
    other_attempt = {**selected, "event_id": "evt-other-attempt", "attempt_no": 2}
    other_run = {**selected, "event_id": "evt-other-run", "run_id": "run-2"}
    events = [selected, other_attempt, other_run]
    before = deepcopy(events)
    result = to_page_observations(events, run_id="run-1", attempt_no=1)
    assert len(result) == 1
    assert "artifact_ids" in result[0]
    assert "secret" not in result[0]
    result[0]["artifact_ids"].append("mutated-output")
    assert events == before


@pytest.mark.parametrize("observation", [
    {**envelope("PageCompleted", stage="page_transcription"), "attempt_no": 0},
    {**envelope("PageCompleted", stage="page_transcription"), "run_id": ""},
    {**envelope("PageCompleted", stage="page_transcription"), "attempt_no": "1"},
])
def test_invalid_observation_scope_is_rejected(observation):
    with pytest.raises((TypeError, ValueError)):
        to_page_observations([observation], run_id="run-1", attempt_no=1)
