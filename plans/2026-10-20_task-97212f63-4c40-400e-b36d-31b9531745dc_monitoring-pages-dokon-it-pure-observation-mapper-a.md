# Plan 2026-10-20: Monitoring pages — pure observation mapper

Implement the missing pure mapper and complete its focused contract matrix, retaining historical proof/results as-is.

## Analysis
- `audit_page_observations.py` is absent; `test_monitor_page_observations.py` imports `to_page_observations` and currently covers basic content-free copy, event allowlists, ordering/filtering, unknown types/stages, and invalid scope.
- The existing module pattern (`audit_events.py`) constructs explicit allowlisted mappings; don't alter it or adjacent audit/read modules.
- Governing contracts: `plans/tasks/2026-10-20_monitor-mvp-{12-page-outcome-events,13-attempt-pages-get,14-cache-reused-event,15-cache-reused-read}.md`; page observations remain bounded-window fragments, and cache reuse remains distinct from inference/completion.
- Prior review `plans/checkpoints/task-b37c64cd-1783-45e6-8daf-f2e6a04e0954.host-review.md` documents absent implementation and incomplete historical proof. Preserve both unchanged.
- Learning `learnings/architecture/2026-10-20_keep-page-observation-mapping-pure-and-window-scoped.md`: preserve order/fragments, require explicit scope, return fresh allowlisted mappings; no second reader or persisted projection.
- No relevant PlantUML diagrams were found. Project verification gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.

## Approach
- Implement only `to_page_observations(observations, *, run_id, attempt_no)` over a finite sequence of already validated content-free mappings.
- Validate requested run/positive attempt scope and reject malformed observation scope; filter valid observations to the requested scope without transforming invalid input into success.
- Publish only StepStarted with `stage=page_transcription`, PageCompleted, PageFailed, and PageCacheReused using exact per-type field allowlists. Preserve window order and distinct observations; omit unknown types/stages and never infer missing state.
- Extend the owned focused test matrix for invalid scopes, unknown stages/types and method/model, cached completed/failed without inference, terminal-only entries, repeated same-page observations, exact allowlists, and deep input immutability.
- Keep all changes within the owned mapper and focused test. Do not touch event/storage/query/listener modules, router/HTTP, dependencies, shared fixtures, OpenAPI, worker, or deployment.

## Implementation
1. Confirm the project interpreter and imports/dependencies work before treating any pytest error as RED; inspect task contracts and current focused tests.
2. Extend `test_monitor_page_observations.py` first, preserving existing assertions and adding the missing contract cases. Capture genuine RED using the loaded `tdd` skill's proof-capture interface under task ID `task-97212f63-4c40-400e-b36d-31b9531745dc`; do not reuse the historical task ID or manually edit proof.
3. Implement the smallest pure mapper in `audit_page_observations.py`; no event classes, I/O, aggregation, latest-selection, synthesized events, or business-state fallback.
4. Capture GREEN with the identical focused argv. Then run the package pytest, both registered backoffice gates, and relevant be-validator-agent/trigger runtime caller tests if their existing fixtures use Moto/fixtures only.
5. Keep historical proof artifacts and unrelated incomplete tests intact; report unrelated collection failures distinctly from focused test results. Do not claim deployed/live completion.

## Testing
- Verify interpreter/dependency imports before proof capture. Use project-root working directory and the caller-specified identical RED/GREEN command:
  `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/ be-document-processing/tests/test_monitor_page_observations.py`
- Run relevant package pytest and registered gates exactly as configured: `npm --prefix apps/backoffice test` and `npm --prefix apps/backoffice run build`.
- Test no latest aggregation or synthetic StepFinished; cache completed/failed remains cache metadata, including when method/model is unknown; unknown event/stage is omitted; malformed scopes reject; all returned items are fresh and input nested values remain unchanged.

## TDD
**Target test:** `be-document-processing/tests/test_monitor_page_observations.py` (pytest). Add cases to the existing focused file before production code.

```python
import pytest

from document_processing.audit.audit_page_observations import to_page_observations


def test_distinct_observations_for_same_page_are_preserved_without_latest_selection():
    first = {"event_id": "evt-a", "type": "PageCompleted", "sequence": 3,
             "occurred_at": "2026-10-20T12:00:00Z", "run_id": "run-1",
             "attempt_no": 1, "page_number": 2, "stage": "page_transcription",
             "duration_ms": 12}
    second = {**first, "event_id": "evt-b", "sequence": 4, "duration_ms": 15}

    result = to_page_observations([first, second], run_id="run-1", attempt_no=1)

    assert [item["event_id"] for item in result] == ["evt-a", "evt-b"]  # RED: mapper absent
```

**Run command:** `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/ be-document-processing/tests/test_monitor_page_observations.py`

| Test case | RED expectation | GREEN expectation |
|---|---|---|
| Existing focused tests plus repeated-page skeleton | Import fails while mapper is absent (only after interpreter/dependency validation) | All output, filtering, purity, and distinct-observation assertions pass |
| Expanded contract matrix | Missing behavior assertions fail against implementation | Invalid scope rejects; unknowns omit; cache statuses and terminal fragments preserve exact allowlisted content without inference |

Implement the TDD cycle using `skill:tdd`; verify accepted RED and GREEN and retain proof under this task ID.

## Files
| Path | Planned change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_page_observations.py` | Add pure scoped observation mapper with per-type allowlists |
| `be-document-processing/tests/test_monitor_page_observations.py` | Complete contract matrix and immutability checks |
| `plans/checkpoints/task-97212f63-4c40-400e-b36d-31b9531745dc.red-green-proof.md` | TDD helper-owned proof; never manually edit |
| `learnings/` | Save a relevant session learning at task completion |

## Progress
- [x] Resolved canonical plan path and reviewed contracts, existing tests, historical host review, and relevant learning.
- [ ] Implement mapper and complete focused TDD contract matrix.
- [ ] Run focused/package tests and registered gates; record actual outcomes.
- [ ] Save at least one learning with `save-learning` after completing the implementation task.
