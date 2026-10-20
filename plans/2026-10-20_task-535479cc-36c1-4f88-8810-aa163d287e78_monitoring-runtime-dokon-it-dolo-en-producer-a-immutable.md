# Plan 2026-10-20: Monitoring runtime producer and immutable context

Determine whether the checked-in canonical validator-agent caller and approved execution identity interface support the requested producer integration. Implement only at a proven compatible seam; otherwise report the exact execution-owner blocker without claiming integration.

## Analysis

- `plans/checkpoints/task-626722a4-f9fd-46a9-8304-17b9f24de1cc.host-review.md` confirms the prior source integration was not delivered; retain its proof/history as-is.
- `plans/monitoring/runtime-producer-context-contract.md` records the current gap: enqueue discards SQS response; claim has no run ID/attempt ordinal; worker passes cached `Options` without per-run context.
- `plans/monitoring/live-trigger-evidence-20261019.md` and `plans/monitoring/next-slices-source-seams-20261019.md` document module-level source evidence but not full image/build provenance, plus the historical trigger candidate. Do not substitute an unrelated worker or restore historical source as live owner.
- The required execution-owner decisions remain confirmed/ambiguous enqueue identity, atomic claim plus attempt semantics under concurrency/crash, and immutable context forwarding. Existing evidence does not authorize a runtime table, counter, outbox, fencing, queue schema, lease, retry, or business behavior change.
- `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` → “Izolace implementace”: business caller passes minimal values at confirmed semantic boundaries; audit event construction, serialization, I/O and fail-open handling remain in the audit package through one injected listener.

## Approach

1. Inspect only owned `be-validator-agent/` source/build caller and its actual focused tests; establish canonical caller/build ownership and whether a compatible authoritative enqueue and claim-attempt interface already exists.
2. If either interface or required concurrency/crash semantics are absent, make no source changes. Update only `plans/monitoring/runtime-producer-context-contract.md` with the exact missing owner decision and smallest required interface, preserving the prior findings and marking the slice blocked.
3. If both interfaces are present and approved, pass immutable execution context explicitly from the successful claim through the actual worker caller into `run_document`/`Options` and downstream execution. Emit RunQueued only for confirmed enqueue and AttemptStarted only for successful atomic claim+attempt; preserve stable logical event identity and failed-claim behavior. Keep audit behavior behind the injected listener and fail-open boundary.
4. Do not change business schema, queue/retry/DLQ/930-second lease semantics, or add identity allocation/recovery machinery. Do not represent mocks, no-op listeners, source/build checks, or old evidence as deployed/live proof.

## Implementation

- First verify the project interpreter and focused-test dependencies/imports before capturing any TDD evidence. A missing interpreter, dependency, or conftest import is an environment blocker, not a genuine RED.
- For an eligible implementation, use actual canonical caller tests for concurrent/duplicate enqueue and claim, confirmed versus ambiguous send, no attempt increment on failed claim, and independent contexts without leakage.
- Differentially run the real business caller with NoOp, functional, and failing-sink listeners; assert identical business writes/order, return/errors, and relevant provider-call counts. Check import direction and ensure audit storage/serialization/error isolation remain under `be-document-processing/src/document_processing/audit/`.
- If no eligible interface exists, document that precise blocker rather than fabricating a failing test or runtime identity. Preserve existing proof artifacts and use only the assigned task ID for any new proof.

## Testing

- Interpreter: `be-document-processing/.venv/bin/python` from repository root; verify imports and dependencies before proof capture.
- Focused pytest argv: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/ <focused-test-filename>`; RED and GREEN must use exactly the same argv if a real interface makes TDD applicable.
- Run relevant package pytest, including actual `be-validator-agent/trigger/tests/` caller tests with AWS dependencies hermetically provided by Moto/fixtures; no live AWS/provider/model/message/replay.
- Run registered gates exactly: `npm --prefix apps/backoffice test` and `npm --prefix apps/backoffice run build`. Report unrelated collection failures separately; do not exclude tests or weaken assertions.
- If implementation is blocked by missing execution-owner contract, report applicable existing checks and the blocker without claiming producer proof or deployment success.

## TDD: skip

This planning task creates a plan only. The implementation's TDD decision is conditional: use genuine RED/GREEN only after a compatible, approved actual caller/interface is established; absent that interface, the task requires a blocker record and forbids fabricated proof.

## Files

| Path | Planned action |
| --- | --- |
| `be-validator-agent/` canonical caller/context source and owned focused tests | Change only if canonical ownership and approved authoritative interfaces are verified; otherwise leave untouched. |
| `plans/monitoring/runtime-producer-context-contract.md` | Record exact unresolved interface/atomicity decision if blocked; preserve existing evidence. |
| `plans/checkpoints/task-535479cc-36c1-4f88-8810-aa163d287e78.red-green-proof.md` | Create only for a genuine authorized TDD cycle after imports/dependencies pass; preserve all old proof files. |

## Progress

- [x] Read the prior contract and host review; identify conditional execution-owner blocker.
- [x] Capture source ownership, audit isolation, and verification constraints in this plan.
- [ ] Implementation agent: verify actual canonical caller and approved interface before source edits.
- [ ] Implement and test actual caller, or record exact blocker with no speculative source changes.
- [ ] Run applicable registered gates and preserve accurately scoped evidence.
