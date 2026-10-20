# Plan 2026-10-20: Integrate trigger monitoring and upstream case lifecycle

Resolve the five trigger conflict files while preserving monitoring identity and upstream case lifecycle as one compatible integration.

## Analysis

- Resolve only file contents in `be-validator-agent/trigger/build.sh`, `common.py`, `template.yaml`, and `tests/conftest.py`; inspect all conflict-marked trigger files and preserve unrelated work. No repository operations, external calls, deployment, or lifecycle actions.
- Trace actual `enqueue_document` callers in stream/backfill and `claim_document` worker branches. `EnqueueResult` and `ClaimResult` are `str` subclasses; keep string equality/hash/count semantics and attached run/execution metadata.
- Preserve execution claims/generation/attempt identity, content-free processing audit, `case_step.py` and `wonderful_webhook.py`, conditional intake/evaluating case transitions, guarded states, webhook disabled/failure behavior, and required environment/IAM.
- Packaging must include `execution_context`, `execution_claims`, document-processing audit, and `wonderful_webhook`; context accepts execution/audit and cases tables with their properties. Template retains local ExecutionTable/audit and upstream CasesTable/webhook permissions. Fixture creates execution and case tables.

## Approach

1. Inspect actual conflict files, adjacent `case_step.py`/`wonderful_webhook.py`, callers, and focused tests before resolving; record genuine incompatibilities with code-path evidence.
2. Resolve both feature sets atomically, preserving current retries/run identity for failed or ambiguous sends; transition case status to intake only after confirmed queue send.
3. Verify claim/audit to case-evaluation flow, conditional state guards, and webhook disabled/failure paths. Add narrowly scoped fake AWS/moto integration coverage only where existing tests do not pin confirmed enqueue→intake or claim/audit→case evaluation.
4. Produce the requested concise integration note under `plans/checkpoints/trigger-integration-20261020/`, including outcome/use-decision chain and exact test evidence.

## Implementation

- Keep `processing_execution_context.EnqueueResult` / `ClaimResult` as string-compatible results; do not invent a metadata incompatibility or replace the protocol with dictionaries.
- Inspect and update only the trigger conflict files and necessary focused tests; preserve remote case modules and local run/request identity behavior.
- Validate no conflict markers remain and both packaging and template/IAM sets survive resolution.
- Run the offline focused trigger suite: upstream `test_case_status` and local execution-owner, enqueue, worker, backfill, DLQ, and template tests. Run registered gate exactly as configured: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; report failures without narrowing selectors or relabeling pre-existing failures.
- No network, live AWS, provider, webhook, credential, deployment, or lifecycle calls.

## Testing

- Inspect conflict-marker-free final contents and verify both feature sets in build packaging, context properties, template resources/permissions, and fixtures.
- Run focused offline trigger tests using fakes/moto, including caller outcomes for confirmed, failed, and ambiguous queue sends and claim/audit case-evaluation behavior.
- Run `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; include exact commands/results and distinguish pre-existing failures.

## TDD: skip

This is conflict-content integration of existing behavior; first inspect current coverage and add only targeted regression cases where the specified interaction is not already tested.

## Files

- `be-validator-agent/trigger/build.sh` — package both execution/audit and webhook modules.
- `be-validator-agent/trigger/common.py` — retain execution/audit and cases table context/properties.
- `be-validator-agent/trigger/template.yaml` — retain ExecutionTable/audit and CasesTable/webhook environment/IAM.
- `be-validator-agent/trigger/tests/conftest.py` — provision both execution and case tables in fixtures.
- Trigger callers, case modules, tests — inspect; modify only for necessary integration fixes or narrow coverage.
- `plans/checkpoints/trigger-integration-20261020/` — write the concise integration outcome and evidence note.

## Progress

- [x] Obtain canonical plan location.
- [x] Capture integration constraints and verification gates.
- [ ] Resolve and verify trigger integration (implementation task).
