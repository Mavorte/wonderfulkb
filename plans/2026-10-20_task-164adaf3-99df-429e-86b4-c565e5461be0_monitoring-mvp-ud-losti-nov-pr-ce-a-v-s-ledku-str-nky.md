# Plan 2026-10-20: Monitoring MVP — page work and outcome events

Add a typed, content-free audit contract and idempotent persistence for observed page transcription starts and terminal outcomes. Do not connect a worker producer.

## Analysis

- `audit_events.py` currently defines immutable `FileReceived`/`RunQueued` contracts, an explicit serialized allowlist, strict envelope validation, and Decimal round-trip handling.
- `audit_storage.py` persists events conditionally by `(case, document, event_id)` and isolates write/serialization failures as unavailable; preserve these semantics for new event types.
- Existing `test_monitor_audit_storage.py` covers storage idempotency and fail-open. Add the requested focused test file without weakening previous coverage.
- Proposal sections `slice-page-outcome`, `signals`, and `instrumentation` set the boundary: `StepStarted` starts only new page work; `PageCompleted`/`PageFailed` are the sole terminal events. Cache reuse and producer hooks are excluded.
- `plans/monitoring/next-slices-source-seams-20261019.md` records source facts separately from design inference and explicitly does not establish deployed-worker equivalence. Treat `be-document-processing/.../pipeline.py:89–102` as checked-in semantic reference only.
- Relevant learnings: `learnings/architecture/2026-10-20_audit-envelope-decimal-round-trip.md` requires strict numeric validation after DynamoDB Decimal reads; `learnings/architecture/2026-10-20_runtime-audit-needs-authoritative-execution-identity.md` reinforces that runtime identity must be authoritative, not synthesized.

## Approach

- Introduce immutable, typed page event contracts using the existing common envelope and producer-supplied stable `event_id`; require `run_id`, positive `attempt_no`, positive `page_number`, and `stage="page_transcription"` where applicable.
- Restrict serialized page payloads to the explicit contract allowlist: optional finite nonnegative monotonic `duration_ms`, proven `method` (`native`/`vision`) and model only when observed, and a safe technical `error_code` on failure. Reject business payloads and arbitrary provider/error text.
- Preserve `occurred_at` as the sole stored event time. Store any authentic outcome independently of missing start/queued/attempt events; never infer failure from missing terminal events or emit events from validation/storage.
- Extend storage’s accepted event types while retaining event-identity idempotency, append-only behavior, and the fail-open boundary around serialization and persistence.
- Preserve caller business result/exception behavior with both NoOp and failing audit boundaries; do not add producer instrumentation or alter pipeline semantics.

## Implementation

1. Add `test_monitor_page_outcome_events.py` first and run the focused RED cycle using `skill:tdd`.
2. Implement page event validation and explicit allowlist serialization/deserialization in `audit_events.py`; ensure integral DynamoDB `Decimal` values round-trip and invalid values fail before mutation.
3. Extend `audit_storage.py` to persist and read these typed events under existing identity/idempotency rules, with no synthetic run/attempt identifiers or extra timestamps.
4. Add only the minimal existing audit-boundary adaptation needed to isolate event construction, validation, serialization, and sink failures from caller outcomes. Do not hook the worker or emit events automatically.
5. Run focused tests, then preserve and run registered gates: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.

## Testing

- Focused Moto/fake tests: native completed; demonstrated vision outcome; pre-call failure with method/model unknown; safe error code; outcome-only fragment; duplicate event; separate pages, attempts, and runs; invalid run/attempt/page/duration/business payload rejected without mutation.
- Verify page terminal outcomes do not create duplicate `StepFinished`/`StepFailed` records, missing starts do not block outcomes, and NoOp/failing audit boundaries preserve caller results.
- Keep all existing audit tests passing. No AWS/inference, producer integration, cloud replay, or broad fault matrix.

## TDD

Implement the TDD cycle using `skill:tdd`; create the targeted test file before implementation and capture RED/GREEN evidence using the canonical proof workflow.

**Test file:** `be-document-processing/tests/test_monitor_page_outcome_events.py`  
**Framework:** pytest with Moto/fakes, matching the existing audit storage tests.  
**Run command:** `cd be-document-processing && python -m pytest tests/test_monitor_page_outcome_events.py -q`

```python
import pytest

from document_processing.audit.audit_events import PageCompleted, PageFailed, StepStarted


def test_page_outcome_requires_positive_attempt_and_page_and_page_stage():
    with pytest.raises(ValueError):
        PageCompleted(
            schema_version=1, event_id="evt-1", case_id="case-1", document_id="doc-1",
            sequence=1, type="PageCompleted", occurred_at="2026-10-20T12:00:00Z",
            run_id="run-1", attempt_no=1, stage="page_transcription", page_number=0,
        )
```

| Test | RED | GREEN |
|---|---|---|
| `test_page_outcome_requires_positive_attempt_and_page_and_page_stage` | Import fails while `PageCompleted` is not implemented. | Invalid page number is rejected with `ValueError`; parallel cases cover invalid attempt/run/stage. |

## Files

| File | Planned change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_events.py` | Add strict typed page-start/completion/failure contracts and safe field allowlists. |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Accept and persist page event types idempotently, retaining fail-open behavior. |
| Existing small audit boundary (identify during implementation) | Isolate any event validation/serialization/sink errors without changing caller outcome; no producer hook. |
| `be-document-processing/tests/test_monitor_page_outcome_events.py` | Add focused contract, serialization, storage, separation, and fail-open tests. |

## Progress

- [x] Load compound-plan workflow, inspect current audit contract/store/tests, proposal, source report, and relevant learnings.
- [ ] Implementation and focused TDD cycle (future task execution).
- [ ] Run registered project gates (future task execution).
