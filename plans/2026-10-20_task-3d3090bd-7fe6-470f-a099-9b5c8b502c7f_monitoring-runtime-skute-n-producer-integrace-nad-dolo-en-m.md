# Plan 2026-10-20: Monitoring runtime producer integration

## Analysis
- Existing evidence in `plans/monitoring/runtime-producer-context-contract.md` and `plans/checkpoints/task-821fe70a-e40f-4fc9-bd11-ced0e5183dde.checkpoint.md` identifies a hard execution-owner interface blocker, not a source-ready implementation seam.
- `Context.send` discards SQS response; enqueue has no stable logical run identity. `claim_document` returns status only and assigns no atomic attempt ordinal; `run_document` receives no immutable per-run context. `trigger/build.sh` does not prove canonical deployed image/build provenance.
- Relevant owned source/test seam if the blocker is resolved: `be-validator-agent/trigger/common.py`, `worker_handler.py`, `tests/test_enqueue.py`, `tests/test_worker.py`; listener implementation remains centralized in `be-document-processing/src/document_processing/audit/` and is outside this change's ownership.
- `learnings/architecture/2026-10-20_attemptstarted-audit-contract-preserves-producer-identity.md`: producer supplies stable event/run identity and positive attempt number; do not derive attempts from SQS receive count, audit rows, or timestamps.
- `learnings/architecture/2026-10-20_runtime-producer-interface-is-a-hard-gate.md` and `learnings/architecture/2026-10-20_monitoring-producer-execution-owner-identity-gate.md`: producer readiness requires explicit execution-owner semantics; retain precise blocker if absent.
- `plans/monitoring/live-trigger-evidence-20261019.md` documents module equivalence but not full-image provenance or authority to replace/fetch source.

## Approach
- First verify whether a canonical owned caller/build and explicitly approved execution-owner interface now exist. Require stable logical run identity, confirmed/definite-rejection/ambiguous enqueue result, atomic claim plus attempt ordinal, concurrency/crash/expired-lease semantics, and immutable context forwarding.
- If any required contract is absent, stop source work; report the exact missing owner decision/interface and leave source and blocker contract unchanged. Do not substitute a permissive fake, generated identity, counter, outbox, lease/fencing, queue schema, or dispatch operation.
- If all interfaces are present, integrate only thin scalar caller/listener boundaries; RunQueued follows confirmed enqueue, AttemptStarted follows successful atomic claim, and context flows explicitly into `run_document/Options`. Preserve business return values, writes/order, exceptions and provider-call counts; central audit code owns event construction, serialization, I/O and fail-open isolation.

## Implementation
1. Inspect the owned trigger caller, build staging, and approved owner interface; compare evidence without fetching/replacing source or treating deployed module hashes as full build provenance.
2. Record a precise blocker and stop unless every execution contract above is authoritative and approved.
3. For an eligible seam only, add caller integration and differential tests for NoOp, functional, and failing sinks; verify confirmed/ambiguous enqueue, duplicate/unclaimed delivery, concurrent claim/attempt behavior, context isolation, and fail-open parity.
4. Preserve historical failed acceptance, proof, and TDD artifacts; use the newly assigned task ID for genuine RED/GREEN through `skill:tdd` after verifying the designated interpreter, imports, dependencies, and canonical package cwd/PYTHONPATH.
5. Run focused trigger tests and registered gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; distinguish collection/environment failures from implementation RED/GREEN.

## Testing
- Eligible interface: hermetic tests only; no provider/live/model/replay/deploy, no scheduler or lifecycle operation.
- Run focused trigger tests with `.venv` Python from the package's canonical cwd/import setup; run the registered backoffice tests/build gate unchanged.
- Differential assertions must compare business writes/order, return values, exceptions, and relevant provider-call counts across NoOp/functional/failing listeners.
- A missing interface is a concrete blocker, not a passing integration test or source-complete result.

## TDD
- Test file: `be-validator-agent/trigger/tests/test_enqueue.py` and `be-validator-agent/trigger/tests/test_worker.py` (extend the existing focused suites).
- Framework: pytest; use project interpreter `be-document-processing/.venv/bin/python` only after confirming required dependencies and package import setup.
- Run command from the canonical trigger package cwd: `../../be-document-processing/.venv/bin/python -m pytest -q tests/test_enqueue.py tests/test_worker.py` (verify exact relative invocation before proof capture; use identical argv for RED and GREEN).
- Skeleton cases: confirmed versus ambiguous enqueue preserves one stable logical identity; failed claim emits no AttemptStarted or ordinal; successful claim forwards immutable context; NoOp/functional/failing listeners preserve business side effects/order/return/exceptions.
- RED/GREEN: each case fails on the missing actual caller behavior before implementation and passes after integration; environment/import/collection failures do not count as RED. Implement cycle and capture evidence using `skill:tdd`; do not invent source behavior when the approved interface is absent.

## Files
- `be-validator-agent/trigger/common.py` — only if canonical enqueue seam and approved outcome/identity interface exist.
- `be-validator-agent/trigger/worker_handler.py` — only if approved atomic claim result and immutable context can be forwarded.
- `be-validator-agent/trigger/tests/test_enqueue.py`, `be-validator-agent/trigger/tests/test_worker.py` — genuine differential caller tests.
- `plans/monitoring/runtime-producer-context-contract.md` — retain as authoritative blocker evidence; update only if an approved interface actually resolves the recorded contract.
- `plans/checkpoints/task-3d3090bd-7fe6-470f-a099-9b5c8b502c7f.red-green-proof.md` — TDD evidence only if implementation is eligible.

## Progress
- [x] Read existing execution-owner contract and prior checkpoint.
- [x] Confirm known blocker and identify owned source/test seams.
- [ ] Verify any newly approved canonical execution interface before source changes.
- [ ] Integrate and validate only if the interface gate passes; otherwise report exact blocker.
