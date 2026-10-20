# Plan 2026-10-20: Monitoring audit event contracts and readback

## Progress

- [x] Canonical plan path reserved.
- [x] Inspected audit contracts, focused tests, host findings and MVP scope.
- [x] Incorporated audit learnings; specified test-first implementation and verification.

## Analysis

- `audit_events.py` contains two top-level `AttemptStarted` definitions and a dead `from_item`; `StepStarted` inherits the shadowed class. Constructor/readback class identity and equality fail in existing source/extraction tests. Host's asserted Decimal failure for the effective `AttemptStarted` decoder contradicts its successful direct Decimal probe: add regression coverage, do not assume that diagnosis.
- `StepStarted/Finished/Failed` cover source_validation/extraction but lack page start; `PageCompleted/PageFailed` are absent, so page-focused pytest cannot collect. `audit_storage.py` accepts the existing types; `audit_queries.py` dispatches solely on persisted `type` through one bounded document Query.
- `FileReceived` envelope, `RunQueued.run_context` (`source` allowlist), conditional event_id put, scoped cursor, one event-time `occurred_at`, NoOp/fail-open boundary and read failures are existing compatibility requirements. Existing test files and audit source are untracked user work: edit narrowly, retain their assertions and unrelated work.
- Use `plans/checkpoints/acceptance-host-review-0818-events-domain.md`, `acceptance-host-review-0818-events-start.md`, `plans/monitoring/mvp-reference-20261019.md` and `next-slices-source-seams-20261019.md` for current facts and scope. Apply learnings `audit-event-dataclass-inheritance.md`, `audit-event-dispatch-and-pytest-runtime.md`, `audit-envelope-decimal-round-trip.md`, and `attemptstarted-audit-contract-preserves-producer-identity.md`; checked-in pipeline is semantic context, not live producer proof. No architecture diagram changes are needed for this internal contract.

## Approach

- Maintain a single `FileReceived` common envelope and one definition per event class; share explicit, type-specific field extraction/validation and integral-Decimal decode for persisted integer fields (`schema_version`, `sequence`, `attempt_no`, `page_number`). Preserve public constructors and valid optional fields; never deserialize pk/sk, arbitrary attributes or raw business data. Keep `RunQueued` serialization behavior unchanged.
- Make Step types share the envelope rather than inherit the shadowed `AttemptStarted` implementation. Permit only `source_validation` and `extraction` without page scope; permit `page_transcription` only on `StepStarted` with positive page_number. Terminal page outcomes are `PageCompleted`/`PageFailed`, never generic Step terminal events. Validate finite nonnegative optional measured duration, `native|vision` method, evidence-backed optional model and approved technical error_code; unknown method/model remain absent/null. Use an allowlisted generic code for unmapped failure, not exception text.
- Retain retry/terminal facts as independent observations: RetryEnqueued requires departing attempt; AttemptFinished has observed status; RunFinished may omit attempt_no for max-attempt terminal. Never infer status, ordering, completion, identity or missing records from sparse audit history. Preserve duplicate immutability and terminal-only/reordered acceptance without cross-event prerequisites.
- Follow `compound-plan` for this document; implementation uses `tdd` for focused proof and `recall-knowledge` guidance. `save-learning` closes implementation after its verification; avoid producer, API, mapper, queue and unrelated-slice edits.

## Implementation

1. Before implementation, inspect current checkout and dependency availability with `be-document-processing/.venv/bin/python`; use only this interpreter for Python tests. Confirm focused test imports collect except for the known page outcome import; distinguish pre-existing errors from semantic RED. Keep old proofs/history untouched.
2. First extend `test_monitor_source_validation_events.py` with the executable regression in TDD below; capture a genuine failing assertion using skill:tdd under this task ID with exactly the same argv for GREEN. Do not use dependency/collection failure as RED or write production code before accepted RED. If capture capability is denied, record the concrete blocker.
3. Consolidate `audit_events.py` duplicate classes/decoders; restore exact subclass roundtrip/equality and strict stage/scope/typed allowlists. Preserve FileReceived/RunQueued scalar/public APIs and fail-open behavior.
4. Extend `test_monitor_page_outcome_events.py` with start/native completion, evidenced vision, pre-call failure with unknown method/model, terminal-only, separate page/attempt/run, duplicate, and forbidden payload/invalid input cases. Add PageCompleted/PageFailed and page-scoped StepStarted; add their minimal accepted types and read dispatch to `audit_storage.py`/`audit_queries.py`.
5. Strengthen focused source/extraction/retry tests with measured duration/Decimal readback, invalid stage/scope/status/code, readback class/equality, isolation, pagination/Query and no synthetic terminal. Where a missing or unexpected constructor argument raises Python `TypeError`, accept `TypeError` only for that explicitly invalid input instead of weakening semantic checks. Test fail-open validation/serialization/write and NoOp without changes to caller result; touch `audit_listener.py` only if its existing seam requires compatibility adjustment.
6. Re-run focused proof GREEN through skill:tdd, then each focused file, combined audit matrix, full Python suite and registered backoffice gates. Record actual commands/results and distinguish unrelated blockers; do not relabel or modify historical failed/inconclusive acceptance. Pure domain scope requires no deployment/live writes.

## TDD

**Edit:** append to `be-document-processing/tests/test_monitor_source_validation_events.py` (existing `audit_table`, `start`, `StepFinished`, `AuditStore` imports/fixture). Run first under skill:tdd with `TASK_ID=task-4ad56e72-4cb9-4180-92a0-19e11177c7a8` from repo root; proof: `plans/checkpoints/task-4ad56e72-4cb9-4180-92a0-19e11177c7a8.red-green-proof.md`.

```python
def test_source_step_readback_preserves_class_and_values(audit_table):
    store = AuditStore(audit_table)
    started = start("evt-regression-1-start")
    finished = StepFinished(
        schema_version=1, event_id="evt-regression-2-finish", case_id="case-1",
        document_id="doc-1", sequence=2, type="StepFinished",
        occurred_at="2026-10-20T12:00:02Z", run_id="run-1", attempt_no=1,
        stage="source_validation", duration_ms=12.5,
    )
    assert store.put(started) == "inserted"
    assert store.put(finished) == "inserted"
    decoded = store.read_document("case-1", "doc-1", limit=10).items
    assert [type(item) for item in decoded] == [StepStarted, StepFinished]
    assert decoded == [started, finished]
    assert all(type(item.attempt_no) is int for item in decoded)
```

**Focused argv for both RED/GREEN:** `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_source_validation_events.py -k test_source_step_readback_preserves_class_and_values`. Capture with `TASK_ID=task-4ad56e72-4cb9-4180-92a0-19e11177c7a8 python3 "$HOME/.config/opencode/skills/tdd/scripts/proof-capture.py" red -- be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_source_validation_events.py -k test_source_step_readback_preserves_class_and_values` and repeat with `green` replacing `red` and identical argv after `--`; `python3` here runs only the approved skill helper, never project pytest. Confirm accepted_red/accepted_green and matching child exit codes/proof; if skill path/capability differs, use the loaded skill's documented supported command, never helper internals.

| Test | RED | GREEN |
| --- | --- | --- |
| `test_source_step_readback_preserves_class_and_values` | Existing shadowed Step hierarchy causes put failure or class/equality assertion failure after actual collection. | Both puts inserted; class identity, value equality and integer attempt_no survive Moto readback. |

Implementace TDD cyklu dle skill:tdd. Add page-specific regression tests before implementing the page contract, but do not claim a page import/collection error as the accepted RED for this proof.

## Testing

- Focused, separately: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_run_queued.py`; repeat for `test_monitor_attempt_started.py`, `test_monitor_source_validation_events.py`, `test_monitor_page_outcome_events.py`, `test_monitor_extraction_events.py`, `test_monitor_retry_terminal_events.py`, `test_monitor_audit_storage.py` under `be-document-processing/tests/`.
- Combined: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_run_queued.py be-document-processing/tests/test_monitor_attempt_started.py be-document-processing/tests/test_monitor_source_validation_events.py be-document-processing/tests/test_monitor_page_outcome_events.py be-document-processing/tests/test_monitor_extraction_events.py be-document-processing/tests/test_monitor_retry_terminal_events.py be-document-processing/tests/test_monitor_audit_storage.py`.
- Entire backend: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests`. Registered gates, in order: `npm --prefix apps/backoffice test` then `npm --prefix apps/backoffice run build`. For direct synthetic Decimal probe only, explicitly set `PYTHONPATH=be-document-processing/src`; do not use system Python for project tests.

## Files

| File | Intended change |
| --- | --- |
| `be-document-processing/src/document_processing/audit/audit_events.py` | Deduplicate definitions; explicit per-type safe contract, roundtrip, page events. |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Accept added page types; preserve conditional put/fail-open behavior. |
| `be-document-processing/src/document_processing/audit/audit_queries.py` | Add page `type` dispatch; preserve bounded document Query/cursor. |
| `be-document-processing/src/document_processing/audit/audit_listener.py` | Modify only if needed for existing fail-open seam. |
| `be-document-processing/tests/test_monitor_{run_queued,attempt_started,source_validation_events,page_outcome_events,extraction_events,retry_terminal_events,audit_storage}.py` | Focused contract, regression, Moto readback and isolation assertions. |
| `plans/checkpoints/task-4ad56e72-4cb9-4180-92a0-19e11177c7a8.red-green-proof.md` | Generated solely by skill:tdd during implementation. |
