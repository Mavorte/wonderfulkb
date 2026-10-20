# Host read-only review — document events GET and lifecycle reducer

**Scope:** actual source review for GET task `9d34c790-5c01-46ba-96d0-bc7f45740763` and lifecycle reducer task `422c4f83-d138-47ea-859b-011f3d86e6e5`. No source/test/config/git/task edits, live calls, deployment, provider calls, or task lifecycle operations were performed. The sole created artifact is this review.

## Verdict

**NOT SAFE / not deliverable as specified.** The lifecycle reducer is a small functioning partial implementation and its current focused tests pass, but substantial required behavior and test matrix are absent. The HTTP GET task remains blocked before implementation, for a documented and source-confirmed lack of trusted case authorization. Do not expose or deploy the route; this is a prerequisite blocker, not an invitation to invent an auth scheme. Neither task meets its specified delivery gates.

## GET `/events` — source and deployment evidence

- `be-intake/app/main.py:126-139` checks only `x-api-key` against service-level `API_KEY`. `CASE_DOCS_PATH_RE` matches the existing documents path. No identity-to-case authorization lookup/interface appears in this middleware.
- `be-intake/app/main.py:152-156` `require_case` validates syntax and checks `cases.get_item(...)` for existence only. It does not establish that this caller may access the case. The existing `be-intake/tests/test_processing_monitor_routes.py` is only a proposed one-test sketch (GET expected 200); it provides no implementation or valid auth/scope characterization.
- No `be-intake/app/processing_monitor_routes.py` or events route registration exists. Search of intake app and document-processing audit source found no `processing/documents` route; the audit package has readers but no HTTP adapter. Thus response schema, `Cache-Control: private, no-store`, per-error headers, pagination/cross-document token enforcement, missing-document behavior and read-error→503 are not implemented at the HTTP boundary.
- `plans/monitoring/task-9d34c790-5c01-46ba-96d0-bc7f45740763-blocker.md` correctly records the auth blocker, no accepted focused test run (its prior Python lacked FastAPI), and no deployment/live attempt. The current authoritative task brief requires package/install, guarded deployment and direct live-function HTTP evidence in this same task; none exists. No source/artifact digest, target revision, recovery/config evidence, authorized synthetic fixture, or live request evidence is recorded. Existing operational host text is explicitly not a hardcoded default and is not evidence of a current target.
- Realistic auth prerequisite: the trusted service-side identity→case authorization interface/decision source must first be identified and made available to this service by its actual owner, with a safe authorized synthetic case/document fixture. Existing `x-api-key`, case existence, and browser-supplied case headers are explicitly insufficient. The source does not establish a particular cookie/JWT/claims/provider scheme; do not invent one. Until that seam is available, keep the route unimplemented/unexposed and do not deploy it. Afterward, continue this same task's existing plan: implement focused auth and endpoint tests, prove reader/package provenance, use the supported existing deploy path with guard/recovery, then directly verify the deployed route against that authorized fixture; do not downgrade the required delivery to source-only.

## Lifecycle reducer — source contract review

Source: `be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py`; focused tests: `be-document-processing/tests/test_monitor_lifecycle_observations.py`.

### What is present

- Pure caller-supplied finite-window processing, no imports/storage/query calls; returns `coverage="partial"`, a descriptive fixed scope, and passes the opaque `next_token` object through unchanged.
- Basic run and attempt grouping; start/retry/run/attempt terminal events remain evidence rather than synthetic starts; publications are separately grouped by `(run_id, publication_id)`.
- Duplicate event `(event_id, sequence)` observations are deduped; conflicting run terminals become `ambiguous`; test evidence currently demonstrates retry/partial publish, run terminal without synthetic attempts, duplicate identity, and one attempt start+terminal. Focused command below passes.

### Required but missing/incorrect

- **Test matrix is incomplete:** only six tests exist. No tests for distinct multiple runs and attempts beyond the simple retry pair, terminal-only attempt, reordered/late fragments, conflicting attempt terminals/result statuses, missing or conflicting scope, publication evidence identity/scope, availability variants, unsupported/read-failure mapping, or a query spy. Existing empty-window test only checks token identity and empty collections.
- **Availability/read failure:** the reducer accepts `unknown`, `not_configured`, `not_instrumented`, but it trusts the caller's string without evidence. The brief requires explicit evidence grounds for not-configured/instrumented; absence alone must remain unknown. There is no read-failure value/error behavior or test; unsupported values raise `ValueError`, which may be acceptable only if HTTP maps genuine source failure to 503, but that ownership/test is not present here.
- **Attempt terminal ambiguity defect:** `AttemptFinished(attempt_status="failed")` is placed into `status_values`, while `AttemptFailed` maps to `"failed"`; single values resolve. `AttemptFinished(attempt_status="partial")` yields `partial`, but there is no documented state semantics test. A duplicate scope conflict/attempt-number inconsistency is not represented as ambiguity; the implementation silently chooses the first non-null attempt number (`next(...)`).
- **Insufficient scope/evidence model:** grouping keys use run and attempt/publication IDs but do not expose or validate case/document scope or sequence ordering. Events with missing `run_id` are absent from summaries (though source says valid mappings); orphan terminal-only attempts with explicit IDs do group. Evidence carries event_id/sequence/type only; no explicit result-status/evidence scope or ambiguity/ordering metadata. Distinct observations for one run remain in evidence, but order/late-event policy is not tested.
- **Deduplication identity semantics:** identity is `(event_id, sequence)` only, as required tests assert only exact duplicate counts once; no conflict behavior is defined when same identity has different payload, and unhashable values fall back to `repr`, whose collision/scope properties aren't characterized.
- Current focused test's orphan-start+terminal test is not terminal-only; it asserts run unknown and evidence, and does not prove the required max-attempt/terminal-only no-synthetic-claim behavior.

## Test execution

From repo root:

1. `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_lifecycle_observations.py` — **PASS, 6 passed** (six deprecation warnings; no functional failure).
2. `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/` — **collection failure** in unrelated `be-document-processing/tests/test_monitor_page_outcome_events.py:3`: it imports `PageCompleted`, `PageFailed`, `StepStarted` from `audit_events.py`, but `PageCompleted` is not defined/exported there. This occurs before full-suite execution; it is not evidence against lifecycle focused behavior. Per task requirements do not exclude or repair this unrelated test within this review.

## Exact remaining scope / disposition

1. GET task: obtain a real service-side trusted identity-to-case authorization seam and authorized synthetic fixture via the legitimate owning interface. Do not infer a mechanism. Then resume endpoint TDD/implementation, verify auth + case/document scope, token binding/pagination, no-store on successes and failures, source failure 503, package/install provenance, and required guarded test deployment/direct live HTTP verification. Until then: **BLOCKED, no route/deploy**.
2. Lifecycle task: complete only its owned pure reducer and focused test file against the detailed partial/ambiguous/evidence/availability/token/no-I/O matrix. Add observable explicit evidence/validation where needed; preserve uncertainty and avoid choosing latest by timestamp/sequence or silently choosing inconsistent scope/attempt metadata. Exercise exact focused GREEN and package suite; record the known full-suite PageCompleted import failure separately, without excluding tests or weakening assertions. No router, AWS/live/deploy changes belong to this reducer task.
3. Parent may register the appropriate task completion roots/terminal overrides; this review does not perform task lifecycle changes.
