# Plan 2026-10-20: Monitoring cache reuse — complete contract matrix

Complete focused PageCacheReused characterization and verification, changing production code only if a required assertion exposes a real contract defect.

## Analysis

- Existing tests in `be-document-processing/tests/test_monitor_cache_reused_events.py` cover Moto roundtrips, changed-payload idempotence, selected invalid inputs, and decimal mapping; previous work fixed artifact ID tuple restoration.
- Missing acceptance coverage: independent run/attempt/page/document scope, required-argument `TypeError`, construction-time no-I/O sentinels, full forbidden-payload exclusion, and bounded fail-open evidence.
- `audit_listener.py` implements only `file_received`; it is the concrete existing fail-open seam and does not prove a PageCacheReused producer exists.
- Use explicit serialization allowlists and persisted-type dispatch; exercise integrally-valued DynamoDB `Decimal` through a real Moto resource roundtrip. A pytest collection/runtime error is not a contract RED.
- Relevant source and prior plan: `audit_events.py`, `audit_storage.py`, `audit_queries.py`, `audit_listener.py`; `plans/2026-10-20_task-73ee7806-e314-4dbf-9474-8b1228b9be04_monitoring-cache-reuse-dokon-it-po-adovanou-valida-n-izola.md`.
- Relevant learnings: `learnings/architecture/2026-10-19_monitoring-filereceived-audit-plan-scope.md` (adapter evidence and scope), `2026-10-20_audit-envelope-decimal-round-trip.md` (Decimal roundtrip), and `2026-10-20_audit-event-dispatch-and-pytest-runtime.md` (allowlists, dispatch, collection diagnostics).

## Approach

- Keep changes focused on hermetic event/store/read characterization; preserve event API, opaque artifact semantics, stable identity, and `occurred_at` as the sole event timestamp.
- Separate run/attempt/page/document cases so each proves its intended scope; assert duplicates retain the original persisted item and create no additional event.
- Assert excluded payload includes page text, blocks, tables, storage keys, URL, errors, and other raw page content; verify no Page/Step terminal events are synthesized.
- Test constructor boundaries with sentinels for cache/model/S3/environment access. Characterize `file_received` no-op/failure behavior using its existing public seam, and state explicitly that it offers no cache-producer guarantee.
- Reuse/link historical genuine RED where applicable; capture fresh GREEN for this task. Do not manufacture a production failure to obtain RED when behavior already works.

## Implementation

1. Extend the focused suite for completed/failed status, native/vision methods, absent/unknown model and artifact references, complete payload allowlisting, and run/attempt/page/document isolation.
2. Add exact omitted-required-argument `TypeError` checks and direct-validator invalid-input checks, including missing run and bool/zero/negative/float attempt/page values; assert rejection precedes persistence.
3. Verify no-I/O construction, no incidental Page/Step terminal events, immutable duplicate handling, explicit event dispatch, and a Moto Decimal put/read roundtrip plus pure mapping.
4. Characterize only the existing `file_received` fail-open responsibility with no-op and failing-sink cases; do not add a cache producer API or imply cache-specific caller coverage.
5. Fix only the affected `PageCacheReused` model, storage, or read-dispatch branch if a genuine contract defect is demonstrated; otherwise retain test-only changes.
6. Record task-specific proof/checkpoint evidence and save a learning after implementation; preserve parent history and existing fixtures.

## Testing

- Focused: `cd be-document-processing && .venv/bin/python -m pytest tests/test_monitor_cache_reused_events.py`
- Backend regression: `cd be-document-processing && .venv/bin/python -m pytest tests`
- Registered project gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`
- Report adapter and hermetic evidence accurately; no live/provider/model/deployment/replay claims.

## TDD

This is testable behavior, but existing implementation already passes some required branches. Use `skill:tdd` for any newly exposed genuine defect, reuse the parent's historical RED rather than recreating it, and capture this task's fresh GREEN. For already-correct branches, document characterization applicability and demonstrate the assertions against the existing implementation without forcing a false failing test.

**Test file:** `be-document-processing/tests/test_monitor_cache_reused_events.py`  
**Run command:** `cd be-document-processing && .venv/bin/python -m pytest tests/test_monitor_cache_reused_events.py`

```python
import pytest

from document_processing.audit.audit_events import PageCacheReused


def test_required_run_id_omission_keeps_constructor_type_error():
    fields = {
        "schema_version": 1, "event_id": "cache-use-1", "case_id": "case-1",
        "document_id": "doc-1", "sequence": 1, "type": "PageCacheReused",
        "occurred_at": "2026-10-20T12:00:00Z", "attempt_no": 1,
        "stage": "page_transcription", "page_number": 1, "cached_status": "failed",
    }
    with pytest.raises(TypeError):
        PageCacheReused(**fields)
```

| Assertion | RED / applicability | GREEN |
|---|---|---|
| Omitted required argument | Reuse parent genuine RED evidence where applicable; this assertion may already pass and must not be made to fail artificially. | Constructor raises `TypeError`, distinct from validator `ValueError`. |
| Missing matrix branches | New assertions expose absent characterization, not necessarily a production failure. Reuse historical RED only for a demonstrated defect. | Isolation, payload exclusions, no-I/O, and bounded fail-open assertions pass. |

Implement genuine RED/GREEN evidence per `skill:tdd`; store follow-up proof under `plans/checkpoints/task-9e2461c6-3177-46d8-b83d-876682e528d3.red-green-proof.md` and link the parent's historical proof where applicable.

## Files

| Path | Planned change |
|---|---|
| `be-document-processing/tests/test_monitor_cache_reused_events.py` | Complete validation, isolation, payload, no-I/O, dispatch, and bounded fail-open matrix |
| `be-document-processing/src/document_processing/audit/audit_events.py` | Conditional narrowly scoped fix if a test proves a model/validation defect |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Conditional narrowly scoped persistence fix |
| `be-document-processing/src/document_processing/audit/audit_queries.py` | Conditional narrowly scoped read-dispatch fix |
| `plans/checkpoints/task-9e2461c6-3177-46d8-b83d-876682e528d3.red-green-proof.md` | Fresh evidence and historical RED provenance |

## Progress

- [x] Read acceptance findings, prior plan, current focused tests, and concrete fail-open seam.
- [ ] Complete the required hermetic test matrix with only evidence-driven source fixes.
- [ ] Run focused, backend, and registered backoffice gates; capture proof and learning.
