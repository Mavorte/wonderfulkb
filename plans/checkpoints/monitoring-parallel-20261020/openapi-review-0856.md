# Independent completion review — task-b96084af-3aa2-438d-a562-900bbdad7e95

**Verdict: MISSING (focused source contract exists and focused test is green; acceptance is not fully complete).** This is a source-only contract review, not an implementation, route/auth, deployment, or live HTTP review. No files other than this note were changed.

## Verification

Ran exactly from repository root:

`be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_openapi_observation_contract.py`

Result: **4 passed, 6 warnings** (library deprecations). The OpenAPI YAML parses and the test's 165(?) structural ref/path assertions pass according to the task checkpoint; this review independently inspected references and schemas but did not run a separate OpenAPI schema validator. The current focused test asserts parse, path allowlist, local-ref resolution, bounded parameters/security/error response presence, broad event allowlists, and lifecycle schema field presence. It does not validate JSON Schema conformance of representative payloads or all event semantics.

The old task `task-e0275532-1050-49c2-b1e3-b787751549bf` host review's original parse failure and generic-schema findings are historical, not current: YAML now parses; event types have individual strict schemas; lifecycle uses separate DTOs; error responses explicitly carry private/no-store. Do not rewrite that historical verdict/proof. Its broader stale task context is not an acceptance gate for this new source-only task.

## Requirements met

- `be-document-processing/contracts/openapi-processing-monitor.yaml:27-123`: exact eight approved paths only (document events, run events, attempts, steps, pages, bounded runs, run detail, document audit); each operation documents explicit scope and returns listed error statuses.
- `:5-19,32,44,56,68-80,92,104,116,133-148`: bounded one-window semantics, partial coverage, empty continuation, 1–100 limit, operation-bound token, no completeness/snapshot/latest/totals claims, trusted-auth interface explicitly unavailable (key is service auth only), and errors including 400/403/404/503 with Cache-Control private,no-store.
- `:167-364`: event variants are individually `additionalProperties: false`, and operation-specific collections restrict item unions. FileReceived has no run_id (`:182-192`); integer attempts/pages and page terminal allowlists are present. Terminal-only observations are allowed by optional other scope fields. `PageCompleted`/`PageFailed` remain distinct page terminal observations; PageCacheReused is separate.
- `:365-400`: separate RunSummary, RunDetail, DocumentAudit DTOs and evidence fields; lifecycle unknown/ambiguous/partial/observed; publication is separate from terminal; no content/raw error/S3 fields.

## Concrete remaining gap

**Run/attempt terminal status values and field names are not faithful to the approved event contract.** `plans/tasks/2026-10-20_monitor-mvp-22-retry-terminal-events.md` specifies AttemptFinished `attempt_status` enum `completed|partial|failed`, and RunFinished `run_status` enum `completed|partial|failed`; RunFinished may omit attempt_no. Current event schemas in YAML use generic unconstrained `outcome: {type: string}` instead:

- YAML `:333-346` AttemptFinished permits only a generic `outcome` string (no `attempt_status`, no enum), while `run_id` and `attempt_no` are optional despite the event brief requiring them for AttemptFinished.
- YAML `:347-359` RunFinished likewise has generic `outcome`, not `run_status` with the specified enum. Its optional `run_id` is itself missing from `required` though event brief says run_id required; attempt_no correctly remains optional here.
- `:193-217`, `:308-332` RunQueued, AttemptStarted, ResultPublished, RetryEnqueued also keep run_id/attempt_no optional and omit some brief-required event scope (`RetryEnqueued` requires run_id and outgoing attempt_no; ResultPublished requires run+attempt and result_status; see `plans/tasks/2026-10-20_monitor-mvp-20-publication-events.md`).
- Step/page contracts are only partly aligned to requirements: the step schemas use generic strings for stage/outcome and omit required run/attempt fields; PageCompleted/Failed omit required stage/page/run/attempt scope (`plans/tasks/2026-10-20_monitor-mvp-12-page-outcome-events.md`). These individual event-field omissions contradict the task's requirement for precise per-event field/status types, although broader unrelated event implementation is out of scope.

This review's **necessary repair scope** is limited to the owned YAML and owned test: add assertions tying each event variant's required scope and status-specific fields to the cited event briefs, with at least AttemptFinished/RunFinished required scope/status enums and ResultPublished/RetryEnqueued required scope/status. Make terminal enum field names align with event brief rather than generic `outcome`. Avoid changing runtime source, routes, auth behavior, unrelated event failures, or broad implementation scope. One caution: the new task's text explicitly lists `RunFinished` and related field rules; it may be useful to test only fields that briefs unambiguously specify, preserving terminal-only exception for missing RunFinished attempt_no.

## Scope/result distinction

This task explicitly calls for a new source-only OpenAPI contract and test, with no route/deploy/HTTP work. Accordingly, lack of live route or deployment proof is **not** a finding against this task. Conversely, focused green and parse/ref checks do not establish exact per-event fidelity, so they do not support COMPLETE. No shared event producer/runtime failure was considered.
