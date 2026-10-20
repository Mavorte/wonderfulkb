# Plan 2026-10-20: Monitoring worker — producer integration repair

Implement only after the execution owner supplies the authoritative execution-context/claim contract; preserve the parent task’s genuine RED evidence and establish fresh GREEN behavior at real callers.

## Analysis

- Parent plan: `plans/2026-10-20_task-d1fa9938-e6eb-4a39-90d1-c580b4e79ad0_monitoring-worker-dokon-it-skute-n-producer-vol-n-a.md`. Parent changes include `be-validator-agent/trigger/tests/test_audit_instrumentation.py`; inspect current committed and uncommitted state before editing.
- Existing focused test checks for `execution_context` on `worker_handler.process_document`. The parent’s failed RED proof and checkpoint are historical evidence; retain them unchanged and do not fabricate a new RED against implemented code.
- `plans/monitoring/runtime-producer-context-contract.md` identifies missing stable enqueue outcome/run identity, atomic claim plus attempt ordinal, explicit immutable context forwarding, and canonical build ownership. It prohibits inferred identity, speculative claim changes, and unapproved outbox/counter/fencing.
- `be-validator-agent/trigger/common.py` owns enqueue/claim calls; `worker_handler.py` forwards execution to `run_document`; `trigger/build.sh` stages worker sources. Verify current symbols and canonical build ownership before choosing actual seams.
- Learnings: `attempt_no` and `run_id` must be producer/owner-issued, never inferred from receive count or timestamps (`learnings/architecture/2026-10-20_attemptstarted-audit-contract-preserves-producer-identity.md`). Keep producer hooks within approved scope (`learnings/architecture/2026-10-19_monitoring-filereceived-audit-plan-scope.md`). Preserve ambiguity rather than inventing lifecycle identity (`learnings/architecture/2026-10-20_bounded-lifecycle-reducer-identity-and-evidence.md`).
- Use `recall-knowledge` before implementation, `tdd` for proof capture, and `validate-implementation` after changes. Registered project gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.

## Approach

Obtain and verify the execution owner’s approved interface and canonical build caller first. If unavailable, report the interface dependency as unresolved and do not claim producers implemented. If available, pass its immutable context directly through supported real worker callers and use exactly one injected fail-open audit listener. Keep enqueue/claim, retry, lease, DLQ, business write order, return values, and failure behavior semantically unchanged.

## Implementation

1. Inspect repository status and parent changes; preserve existing code and historical proof. Verify current caller/build provenance and request the authoritative owner contract for stable run identity, confirmed/failed/ambiguous enqueue outcomes, atomic claim/attempt assignment, and retry/crash semantics.
2. Map each supported real caller to its owner-issued context and event boundary. Include only facts confirmed by that boundary; leave unsupported paths explicitly unsupported.
3. Extend the existing audit package’s event/listener boundary only as needed. Inject one listener through the canonical worker composition root; isolate listener construction, validation, serialization, and sink errors without changing execution outcomes.
4. Update actual caller tests for successful/failed claim, context forwarding, and functioning/failing sink behavior. Compare business writes/order, return/error, and provider calls against NoOp behavior.
5. Include the existing audit package in the canonical worker artifact only if current build ownership confirms the correct build path; verify hermetic import/build and document supported/unsupported source evidence in `plans/monitoring/worker-instrumentation-contract.md`.
6. After focused GREEN, run relevant worker/audit suites and the registered backoffice test/build gate. Keep source/build evidence distinct from deployed/live evidence; do not deploy or perform live writes in this acceptance repair unless separately authorized by the applicable task scope.

## Testing

- Focused command (same argv for proof phases): `be-document-processing/.venv/bin/python -m pytest be-validator-agent/trigger/tests/test_audit_instrumentation.py -q` (confirm interpreter/dependencies and repository cwd/PYTHONPATH first).
- Verify real caller behavior with NoOp, recording, and raising listeners; assert exact owner context/event values, no event on unsuccessful claim, and unchanged business effects/results/errors/provider-call counts.
- Run relevant worker and audit package tests, then `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- Preserve the parent RED/checkpoint unchanged; capture and read back a new task-scoped RED-to-GREEN proof linking the historical genuine RED and fresh GREEN with identical focused command/argv. Do not label prior incomplete proof as complete.

## TDD

Use `skill:tdd`. Reuse the parent’s genuine historical RED as provenance; after this task’s implementation, capture fresh GREEN with the same focused command and retain the complete evidence under this task ID.

**Test file:** `be-validator-agent/trigger/tests/test_audit_instrumentation.py`  
**Framework:** pytest (existing focused worker test).  
**Run command:** `be-document-processing/.venv/bin/python -m pytest be-validator-agent/trigger/tests/test_audit_instrumentation.py -q`  
**Edit hint:** extend the existing focused test after confirming the authoritative contract and real worker caller API.

```python
from trigger import worker_handler


def test_process_document_forwards_owner_execution_context():
    # Use the actual context type/factory and listener injection point approved by
    # the execution owner; assert the exact supplied context reaches the real caller.
    assert worker_handler.process_document  # RED: replace with behavioral caller assertion
```

| Test | RED / historical evidence | GREEN |
|---|---|---|
| Real worker forwards owner-issued context and emits the supported producer event | Link the parent’s genuine RED; do not rerun or recreate it as a false pre-implementation state | Exact owner context and expected event observed at actual caller |
| Unsuccessful claim emits no start event | Existing/added caller behavior fails if it fabricates context or emits before confirmed claim | No producer call/event; existing claim result preserved |
| Raising audit sink is fail-open | Fails if listener exception changes execution result/effects | Business writes/order/result/error/provider calls match NoOp |

## Files

| Path | Planned change |
|---|---|
| `be-validator-agent/trigger/common.py`, `worker_handler.py`, canonical composition/build files | Forward only approved owner-issued context and inject the single listener at supported actual boundaries. |
| `be-document-processing/src/document_processing/audit/` | Add only required event/listener support with centralized fail-open isolation. |
| `be-validator-agent/trigger/tests/test_audit_instrumentation.py` and relevant worker tests | Test actual caller behavior and NoOp/recording/raising listener equivalence. |
| `be-validator-agent/trigger/build.sh` (only if confirmed canonical) | Package/import existing audit code in the verified worker artifact. |
| `plans/monitoring/worker-instrumentation-contract.md` | Record source-backed supported and unsupported caller/build evidence. |
| `plans/checkpoints/task-cf78ff7a-20a9-4053-bc3c-712066c4c7d1.red-green-proof.md` | Store new proof, linking historical parent RED and fresh same-command GREEN. |

## Progress

- [x] Read the parent plan, checkpoint, focused RED test, runtime contract, and relevant learnings.
- [x] Identify authoritative-context prerequisite and preservation requirements.
- [x] Define focused behavior tests and verification gates.
- [ ] Confirm owner contract/build provenance before implementation.
- [ ] Implement supported callers and capture fresh GREEN proof.
