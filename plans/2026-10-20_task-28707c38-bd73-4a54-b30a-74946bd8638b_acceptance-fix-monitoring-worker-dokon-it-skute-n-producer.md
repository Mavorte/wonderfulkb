# Plan 2026-10-20: Monitoring worker producer acceptance repair

Implement verified producer hooks only after the execution owner supplies the missing authoritative context and build contract; preserve all existing changes and historical RED evidence.

## Analysis

- Original plan: `plans/2026-10-20_task-cf78ff7a-20a9-4053-bc3c-712066c4c7d1_monitoring-worker-dokon-it-skute-n-producer-vol-n-a.md`. Its blocker is still reflected in `plans/monitoring/runtime-producer-context-contract.md`.
- `trigger/common.py` currently discards SQS send response and claim returns status only; `worker_handler.py` calls `run_document` with warm-cached options. No stable run identity, atomic attempt ordinal, or immutable per-execution context is available.
- The existing `be-validator-agent/trigger/tests/test_audit_instrumentation.py` only introspects a function signature; replace/extend it with actual caller behavior after the owner contract exists.
- Relevant learning: `learnings/architecture/2026-10-20_worker-audit-integration-owner-identity-gate.md` prohibits invented identities and signature-only proof. Preserve parent genuine RED at `plans/checkpoints/task-d1fa9938-e6eb-4a39-90d1-c580b4e79ad0.red-green-proof.md` unchanged.

## Approach

1. Confirm the execution owner’s approved enqueue outcome/run identity, atomic claim+attempt result, immutable context forwarding, retry/crash semantics, and canonical build ownership. Do not implement producer behavior while any required interface is absent.
2. Once approved interfaces exist, instrument only supported actual enqueue and successful-claim callers with one injected fail-open audit listener. Preserve queue, claim, retry, lease, DLQ, business-write ordering, return values, and errors.
3. Demonstrate behavior at callers: confirmed enqueue, rejected/ambiguous send policy as specified, successful and unsuccessful claims, exact context forwarding, and equivalent outcomes with NoOp, recording, and raising sinks.
4. Package audit dependencies only through the verified canonical worker build path; record supported caller/build evidence.
5. Link the genuine historical RED and capture fresh GREEN under this task with the exact same focused command; never manufacture a new RED against already-existing behavior.

## Implementation

- Inspect current caller changes and owner contract before editing; do not revert unrelated working-tree changes.
- Add/adjust behavioral pytest cases before the implementation-specific producer changes, using only approved contract types and injection seams.
- Implement the smallest context pass-through and central fail-open listener integration; assert unsuccessful claims emit nothing and sink failures do not alter business execution.
- Verify package/build provenance, focused tests, relevant worker/audit suites, then `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- If the contract remains unavailable, retain the blocker explicitly; do not report implementation or GREEN completion.

## Testing

- Focused command: `be-document-processing/.venv/bin/python -m pytest be-validator-agent/trigger/tests/test_audit_instrumentation.py -q` (confirm its environment and imports before proof capture).
- Behavioral assertions: actual enqueue/claim boundary calls and exact context; no producer event on failed claim; NoOp/recording/raising listener preserve business writes, ordering, result/error, and provider call counts.
- Run relevant trigger worker/audit tests and the registered backoffice test/build gate.
- Read back task-scoped proof linking the parent RED and same-command fresh GREEN; keep incomplete historical proof labeled incomplete.

## TDD

Use `skill:tdd`. Preserve the historical genuine RED as provenance; capture fresh GREEN after behavior implementation with the exact focused command below. Do not fabricate a RED because implementation already exists.

**Test file:** `be-validator-agent/trigger/tests/test_audit_instrumentation.py`  
**Framework:** pytest.  
**Run command:** `be-document-processing/.venv/bin/python -m pytest be-validator-agent/trigger/tests/test_audit_instrumentation.py -q`  
**Edit hint:** Replace signature-only introspection with real caller tests once the approved context/listener interface is available.

```python
from trigger import worker_handler


def test_successful_claim_forwards_owner_context_and_emits_attempt_started(worker_context, recording_listener):
    result = worker_handler.process_document(
        case_id="case-1",
        document_id="doc-1",
        execution_context=worker_context,
        audit_listener=recording_listener,
    )
    assert recording_listener.events == [expected_attempt_started(worker_context)]  # RED until real caller emits approved event
```

| Behavior | Expected failure before implementation | Expected pass |
|---|---|---|
| Successful claim forwards owner-issued context and emits supported event | Actual caller does not forward context/emit event | Exact approved context/event observed |
| Unsuccessful claim emits no start event | Caller emits before confirmed claim | No event; claim result unchanged |
| Raising sink is fail-open | Sink exception changes execution | Same effects/result/error as NoOp |

## Files

| Path | Planned change |
|---|---|
| `be-validator-agent/trigger/common.py`, `worker_handler.py`, canonical composition/build files | Integrate only owner-approved context and producer seams; preserve execution semantics. |
| `be-document-processing/src/document_processing/audit/` | Reuse/extend central listener behavior only as required for injection and fail-open isolation. |
| `be-validator-agent/trigger/tests/test_audit_instrumentation.py` and relevant worker tests | Add caller-level behavioral coverage. |
| `plans/monitoring/worker-instrumentation-contract.md` | Record verified supported callers and canonical build provenance. |
| `plans/checkpoints/task-28707c38-bd73-4a54-b30a-74946bd8638b.red-green-proof.md` | Record historical RED linkage and fresh same-command GREEN evidence. |

## Progress

- [x] Read original plan, checkpoint, worker contract, existing test, and relevant learning.
- [x] Preserve unrelated/uncommitted repository state; determine existing authoritative-context blocker.
- [ ] Obtain and verify owner contract/build provenance.
- [ ] Add real caller behavior tests, implement supported hooks, and capture complete proof.
