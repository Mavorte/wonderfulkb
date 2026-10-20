# Plan 2026-10-20: Monitoring lifecycle — canonical run status and lossless conflict evidence

Complete the bounded pure lifecycle reducer against the actual audit event mappings while keeping historical acceptance and proof artifacts intact.

## Analysis
- `audit_lifecycle_observations.py` currently collapses all `RunFinished` states to `finished`, deduplicates conflicting payloads by first occurrence, and can split/overwrite attempt scope.
- `AttemptFinished.to_item()` exposes `run_id`, `attempt_no`, `attempt_status`; `RunFinished.to_item()` exposes `run_id`, `run_status`, optional `attempt_no` (`audit_events.py:317-375`, read-only contract source).
- Keep runs, attempts, and publication summaries separate; only summarize supplied finite window, always partial, preserve opaque token, never infer absolute latest or whole-history completeness.
- Prior independent review `plans/checkpoints/monitoring-parallel-20261020/lifecycle-review-0856.md` documents the missing cases; prior failure/acceptance/TDD evidence remains historical.
- Relevant learning: producer-supplied attempt identity is authoritative; do not derive it from row counts, receive counts, or mutable timestamps (`learnings/architecture/2026-10-20_attemptstarted-audit-contract-preserves-producer-identity.md`). Event envelope Decimal detail is adapter-specific and not a reason to broaden this reducer (`learnings/architecture/2026-10-20_audit-envelope-decimal-round-trip.md`).
- No applicable PlantUML diagram was located. Relevant workflow skills: `tdd` for genuine RED/GREEN proof and `save-learning` after delivery.

## Approach
- Preserve the current public summary shape where possible; choose a small explicit validation/uncertainty and read-failure contract compatible with current API rather than introducing event aliases, stored event changes, I/O, or HTTP behavior.
- Deduplicate equivalent `(event_id, sequence)` observations only. When identity collides with different payloads, retain evidence and make affected conclusions ambiguous independent of input order, including late/reordered bounded fragments.
- Interpret canonical `run_status` values (`completed|partial|failed`) and canonical attempt scope `(run_id, attempt_no)`. Validate missing/contradictory scope, attempt-number identity conflict, and invalid status without choosing a winner.
- Require explicit caller evidence for `not_configured` / `not_instrumented`; empty observations mean unknown. Represent source-read failure explicitly for later caller-to-HTTP-503 mapping; reducer performs no I/O.
- A `RunFinished.attempt_no` never creates an attempt. An `AttemptFinished` without a start remains an observed terminal-only attempt and does not imply start or complete history.

## Implementation
1. Start a new genuine RED/GREEN cycle using `skill:tdd`'s permitted interface, with the project interpreter and unchanged exact argv for both captures; retain previous task artifacts unchanged.
2. Extend the existing focused matrix with canonical run outcomes, equivalent vs payload-conflicting duplicate identities, reorder/late bounded fragments, invalid/missing/contradictory attempt scope and status, terminal-only separation, explicit availability evidence, and read failure.
3. Implement only the pure reducer and its explicit small public result/validation contract; do not edit event serializers, reader, routers, callers, fixtures, or other modules.
4. Preserve all 12 current tests/assertions and add the complete requested scope/evidence/availability matrix, including no inferred latest, unknown empty window, partial coverage, and opaque token identity.
5. Capture own proof at `plans/checkpoints/task-d6b1100a-d1eb-4e95-8618-85cb3380f560.red-green-proof.md`; save a concise learning after completion. Keep evidence artifacts Markdown/JSON only.

## Testing
- Use only `be-document-processing/.venv/bin/python`; no system interpreter fallback.
- RED and GREEN, same argv: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_lifecycle_observations.py`.
- Then run the focused test and full package suite: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests`.
- Run registered gates: `npm --prefix apps/backoffice test` and `npm --prefix apps/backoffice run build`.
- Preserve unrelated failures and collection errors as-is; report them separately from reducer results. No live HTTP/provider/AWS, replay, deployment, or runtime-success claims.

## TDD
Implement the RED/GREEN cycle using `skill:tdd`'s supported interface; do not bypass permissions or inspect its external helper internals. Genuine RED must prove missing reducer semantics, not dependency or collection failure. Save new proof under this task ID and retain historical failed/inconclusive results unchanged.

**Test file:** `be-document-processing/tests/test_monitor_lifecycle_observations.py`  
**Framework:** pytest (existing focused suite)  
**Run command:** `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_lifecycle_observations.py`  
**Edit hint:** Append within the existing module; retain all 12 existing cases.

```python
from document_processing.audit import audit_lifecycle_observations as lifecycle


def test_run_finished_preserves_canonical_run_status():
    item = {
        "schema_version": 1,
        "event_id": "run-terminal",
        "case_id": "case-1",
        "document_id": "doc-1",
        "sequence": 1,
        "type": "RunFinished",
        "occurred_at": "2026-10-20T12:00:01Z",
        "run_id": "run-1",
        "run_status": "partial",
    }
    summary = lifecycle.reduce_observations([item], next_token="cursor")
    assert summary.runs[0].state == "partial"  # RED: current reducer drops run_status and returns finished
```

| Case | RED | GREEN |
|---|---|---|
| Canonical `RunFinished.run_status=partial` | Current output incorrectly says `finished` | Run summary retains `partial` and evidence |
| Same identity, conflicting payload | Current dedupe discards one fact | Both facts retained and affected result ambiguous, order-independent |
| Attempt missing/contradictory scope or invalid status | Current grouping can claim or split definite attempt | Explicit validation or uncertainty preserves evidence without winner |
| Run terminal with attempt number / terminal-only attempt | Current run terminal can synthesize attempt | No synthesized attempt; real terminal-only attempt remains partial observation |
| Availability and source failure | Bare availability accepted / read failure lacks explicit result | Caller evidence required; absence unknown; explicit error path, no I/O |

After GREEN run the full package suite and both registered backoffice gates; never suppress existing assertions or failures.

## Files
- `be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py` — correct pure reducer semantics and minimal public uncertainty/error contract.
- `be-document-processing/tests/test_monitor_lifecycle_observations.py` — preserve 12 tests and complete the documented contract matrix.
- `plans/checkpoints/task-d6b1100a-d1eb-4e95-8618-85cb3380f560.red-green-proof.md` — new task-owned proof only.
- `learnings/` — concise learning saved via `save-learning` after implementation.
- `plans/2026-10-20_task-d6b1100a-d1eb-4e95-8618-85cb3380f560_monitoring-lifecycle-canonical-run-status-a-neztr-tov.md` — this plan.

## Progress
- [x] Resolve canonical plan path and inspect review, reducer, focused tests, event serializer, and relevant learnings.
- [x] Define constrained implementation and verification approach.
- [ ] Implement with genuine task-owned RED/GREEN evidence.
- [ ] Run full relevant Python and registered backoffice gates; preserve outcomes accurately.
- [ ] Save learning after implementation.
