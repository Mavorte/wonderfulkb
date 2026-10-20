# Acceptance host review — RunQueued / AttemptStarted (2026-10-20)

Read-only inspection of current checkout against `plans/tasks/2026-10-19_monitor-mvp-06-run-queued-event.md` and `...08-attempt-started-event.md`, plus their task-owned plans/checkpoints/proof and complete current audit event/store/query implementation + focused tests. No source/test/task-state edits and no cloud/deploy calls. Only this review note was written.

## Findings / disposition input

- **RunQueued implementation: SAFE / complete for the scoped contract.** `audit_events.py:60-95` requires caller-supplied nonblank run_id, keeps the common envelope and only serializes nonempty `source` run_context; unknown keys are excluded. DynamoDB numeric envelope values are decoded. `audit_queries.py:80-95` type-dispatches it while preserving the single bounded document Query (`:63-76`). Storage has conditional event_id idempotence and document-key scope (`audit_storage.py:43-63`). FileReceived remains compatible.
- **AttemptStarted implementation: NOTSAFE / incomplete in the current source despite earlier successful checkpoint.** There are *two* `AttemptStarted` class definitions at `audit_events.py:99` and `:211`; the later class shadows the first. The effective later `from_item` at `:228-237` sets `value` from `item['attempt_no']`, but only converts a Decimal when integral and does not convert it before passing `attempt_no=value`; boto3/Moto returns Decimal for DynamoDB numbers. The effective constructor enforces positive strict int, so readback raises ValueError for a persisted valid attempt. The earlier shadowed implementation has unrelated/broken decoding (attempt to pass run_context to class without that field); remove duplicate and retain a single correct implementation. Minimum repair: exactly one AttemptStarted definition, with `from_item` converting integral Decimal attempt_no to int before construction, no unrelated run_context; keep explicit producer ID and strict attempt validation. Add/use a regression that asserts Moto document read round-trip, not merely store put.
- **Historical proof remains historical, not invalidated or rewritten.** Recorded RunQueued GREEN: 3 passed. Recorded AttemptStarted GREEN: 7 passed. Current checkout differs from claimed AttemptStarted proof state (duplicate definitions are visible now), so current live test result governs. No attempt to alter historical artifacts.
- No basis for new independent completion root: this is a bounded repair to the existing AttemptStarted acceptance scope, not a missing independent requirement. Existing scope explicitly excludes producer/live integration and does not claim attempt counter increment.

## Verification run against current source

From repo root, using requested `be-document-processing/.venv/bin/python`:

- `... -m pytest -q be-document-processing/tests/test_monitor_run_queued.py be-document-processing/tests/test_monitor_attempt_started.py` → **10 passed** (6 dependency deprecation warnings, 34.65s). Note: AttemptStarted test currently round-trips and returns same Decimal-construction object comparison behavior in Moto; it did not expose the effective decoder issue because data roundtrip equality doesn't ensure decoded integer type/strict reconstruction path. Source-level defect noted above; a direct decode probe should validate once repair is made.
- `... -m pytest -q be-document-processing/tests/test_monitor_audit_storage.py` → **30 passed** (6 deprecation warnings, 17.75s).

## Evidence pointers

- Canonical brief requirements: plans/tasks `2026-10-19_monitor-mvp-06-run-queued-event.md`, `2026-10-19_monitor-mvp-08-attempt-started-event.md`.
- Task-owned checkpoint says RunQueued focused proof GREEN (3); AttemptStarted checkpoint says 7 tests + broader regression were green.
- Proof artifacts preserve original RED/GREEN outputs: `plans/checkpoints/task-db71cc4e-dc83-4457-8119-8bf72e2fa1a7.red-green-proof.md` and `plans/checkpoints/task-e1e34fde-82b5-43aa-a744-aef7b5858293.red-green-proof.md`.
- Current inspected code line references are `be-document-processing/src/document_processing/audit/audit_events.py:60-135,211-237`, `audit_queries.py:63-95`, `audit_storage.py:43-71`.
