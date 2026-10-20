# Lifecycle reducer independent review (2026-10-20 09:23)

## Verdict: MISSING

Read-only inspection; no source, test, config, task, git, provider, or deploy writes. Only this Markdown review was authored. The reducer file and focused tests are untracked in the worktree (pre-existing); they were not modified.

## Evidence

- `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_lifecycle_observations.py` → **18 passed, 6 warnings**.
- Canonical serializers in `be-document-processing/src/document_processing/audit/audit_events.py`: `AttemptFinished.to_item()` emits `run_id`, `attempt_no`, `attempt_status`; validated attempt statuses are completed/partial/failed. `RunFinished.to_item()` emits `run_id`, `run_status`, and optional `attempt_no`; run statuses are completed/partial/failed. No legacy `AttemptFailed`/`RunFailed` serializer or `ResultPublished` class was found in this event module. Do not infer caller capability from empty observations.
- Source inspection: `audit_lifecycle_observations.py` has caller-evidence validation for non-unknown availability and raises `RuntimeError` on supplied `read_error`. Duplicate equivalent payloads are deduped; distinct same `(event_id, sequence)` payloads retained and mark grouped run/attempt ambiguous. `coverage` is always partial and `next_token` is passed through.
- Reducer uses `run_status` for `RunFinished`; RunFinished's optional attempt number does not create an attempt. Canonical AttemptFinished uses `attempt_no`/`attempt_status` and terminal-only rows can form an attempt observation.
- Probe command used project interpreter and explicit `PYTHONPATH=be-document-processing/src`; scenarios: equivalent duplicate, conflicting same identity, conflicting attempt number across event IDs, contradictory start identity+number fields, missing run scope, invalid attempt status, terminal-only attempt, run_status partial/invalid, RunFinished optional attempt_no.

## Probe results / gaps

| Requirement | Observed | Verdict |
|---|---|---|
| Equivalent duplicate | One attempt/evidence retained | Pass |
| Same identity conflicting payload, both payload orders | Ambiguous, both evidence entries retained | Pass (focused tests cover both orderings for run terminal payloads) |
| RunFinished canonical partial status | Run state `partial` | Pass |
| RunFinished optional attempt_no | No attempt synthesized | Pass |
| Terminal-only canonical AttemptFinished | One failed attempt evidence; no start fabricated | Pass |
| Missing attempt run_id | No run/attempt summary emitted; evidence silently lost | **Missing**: required uncertainty/partial evidence, not a definite empty result |
| Invalid canonical attempt status | Attempt becomes `ambiguous`, evidence retained | Pass conservatively; test coverage should pin actual behavior |
| Invalid RunFinished status | Run becomes ambiguous | Pass conservatively; test coverage should pin actual behavior |
| Same run with terminal attempt_no 1 and 2 | Two individually definite failed attempts, no identity/scope ambiguity | **Missing**: brief requires contradictory supplied identity/number not split into certain facts |
| AttemptStarted with contradictory `attempt_no=1` and legacy `attempt_number=2` | Creates a certain attempt at number 2; a terminal at 1 remains separately certain | **Missing**: canonical input validation/uncertainty must prevent this split. `attempt_number` is not canonical serializer field; do not normalize it as a new contract.
| Availability evidence and read-error | Bare `not_configured` raises ValueError; explicit read_error raises RuntimeError | Source contract present; caller capability must be supplied by caller, not inferred |

Scope relation: the tests include 18 cases and preserve the 12 earlier cases (task text states 12 as prior baseline); tested additions cover some, not every gap. Runtime availability provenance and actual read-failure mapping are outside this pure reducer review; no HTTP/runtime claim made.

## Minimal remaining repair

Within the originally permitted source/test paths only: preserve explicit evidence and uncertainty for malformed/missing scope instead of dropping it; detect cross-fragment contradictory run/attempt number identity without relying on order; validate canonical `AttemptStarted` number scope and prevent legacy `attempt_number` from becoming an unsupported fallback. Add focused assertions for these exact cases while retaining existing assertions. Then rerun the same focused command. No changes were made in this review.
