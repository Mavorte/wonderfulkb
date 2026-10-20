# Plan 2026-10-20: FileReceived audit persistence acceptance repair

Complete only the missing internal audit-store slice, preserving the original task's scope and existing test work.

## Analysis

- The prior task added `be-document-processing/tests/test_monitor_audit_storage.py` but no audit modules or template configuration; leave that existing test work intact and fill its missing production contract.
- The existing tests cover conditional idempotency, document isolation, bounded pagination, and read-error propagation. Extend them only for uncovered config, timeout, and continuation-scope requirements.
- Follow `plans/monitoring/mvp-reference-20261019.md`: seven-field FileReceived envelope, separate audit table, stable identity, document-partition Query with limit 1–100 and scope-bound continuation; no producer hook, HTTP, deployment, TTL, run projections, or Scan.
- `template.yaml` currently defines the document table and per-function IAM. Add only the audit table, opt-in/disabled setting, finite SDK timeout setting, and least-privilege table actions required by the store.
- Relevant patterns: `config.py` environment-backed `Settings`; `test_aws_storage.py` Moto DynamoDB setup. No diagram for this persistence slice was identified.
- Learnings: audit scope rules in `learnings/architecture/2026-10-19_monitoring-filereceived-audit-plan-scope.md` and `...audit-store-scope.md`; do not call setup/collection failures valid RED (`learnings/test-failures/focused-pytest-capture-environment-blockers.md`). Recall search used local fallback; QMD collection was unavailable.

## Approach

- Implement the narrow `document_processing.audit` package and adapter against the existing contract test.
- Persist only `schema_version`, `event_id`, `case_id`, `document_id`, `sequence`, `type`, and `occurred_at`; use document partition plus stable event identity as keys and conditional put so a duplicate cannot overwrite the first event.
- Query one document only, enforce limit 1–100, and encode continuation state opaquely with case/document/query scope binding; reject malformed or mismatched continuation tokens.
- When audit storage is not configured, expose an explicit disabled store behavior. Configure finite boto3 connection/read timeouts; allow read failures to propagate.
- Keep infrastructure changes in the existing SAM template and constrain IAM to the audit table and needed DynamoDB actions.

## Implementation

1. Inspect the existing focused tests and parent proof artifacts. Preserve prior evidence; reuse genuine historical RED only if it represents the expected behavior failure. Do not relabel the recorded missing-dependency collection failure as RED.
2. Ensure the focused pytest environment has its test dependencies; inspect stderr and establish behavioral RED for missing audit behavior before production edits. If dependency installation remains blocked, record the exact blocker without manufacturing proof.
3. Add/adjust focused tests for disabled configuration, bounded limits, document-bound continuation rejection, and finite client timeouts while retaining the existing round-trip, duplicate, scope, paging, Query-not-Scan, and error assertions.
4. Implement `audit_events.py`, `audit_storage.py`, and `audit_queries.py`, integrating settings and constructing the DynamoDB adapter with explicit finite timeouts.
5. Update `template.yaml` with the audit table and only the required environment/IAM configuration; validate the template and run focused tests.
6. Capture fresh GREEN evidence and run the registered gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; report any blocked checks as such.

## Testing

- Focused: `cd be-document-processing && python3 -m pytest -q tests/test_monitor_audit_storage.py` (same argv for paired RED/GREEN proof).
- Confirm duplicate put preserves the first record; reads are document-scoped and paginated within each requested limit; continuation tokens cannot be reused across case/document/query scope.
- Confirm disabled configuration is explicit, boto3 timeout values are finite, read exceptions propagate, and adapter calls Query rather than Scan.
- Validate SAM template syntax and IAM/table wiring; run registered gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- Separate mocked adapter evidence from any claim of deployed persistence; this plan's slice does not include deployment or live AWS writes.

## TDD

**Test file:** `be-document-processing/tests/test_monitor_audit_storage.py`  
**Framework:** pytest with Moto and focused fakes (already used by the existing test).  
**Run command:** `cd be-document-processing && python3 -m pytest -q tests/test_monitor_audit_storage.py`  
**Edit hint:** Extend the existing test module; it already has behavioral assertions but currently imports missing production APIs.

```python
import pytest

from document_processing.audit.audit_events import FileReceived
from document_processing.audit.audit_storage import AuditStore


def test_continuation_token_is_bound_to_document(audit_table):
    store = AuditStore(audit_table)
    store.put(FileReceived(
        schema_version=1, event_id="evt-1", case_id="case-1",
        document_id="doc-1", sequence=1, type="FileReceived",
        occurred_at="2026-10-19T12:00:00Z",
    ))
    page = store.read_document("case-1", "doc-1", limit=1)
    assert page.next_token is not None
    with pytest.raises(ValueError, match="scope"):
        store.read_document("case-1", "doc-2", limit=1, next_token=page.next_token)
```

| Test | Expected RED | Expected GREEN |
|---|---|---|
| Existing round-trip/duplicate test | Missing audit API or behavioral mismatch (not dependency collection failure) | Same first event returned once, unchanged |
| Existing document paging test | Missing API, cross-document results, or broken continuation | Correct isolated pages within limit |
| Continuation scope test | Token accepted for another document | Scope mismatch rejected |
| Query failure/operation test | Error swallowed or Scan used | Query only; original read exception propagates |
| Disabled store and timeout tests | Missing/ambiguous config or unbounded client | Explicit disabled state and finite timeout values |

Implement the captured RED/GREEN cycle using `skill:tdd`; retain prior proof artifacts as history and add fresh follow-up evidence.

## Files

| Path | Change |
|---|---|
| `be-document-processing/src/document_processing/audit/__init__.py` | Define the internal audit package |
| `be-document-processing/src/document_processing/audit/audit_events.py` | FileReceived envelope and field validation |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Explicit disabled behavior, configured DynamoDB client/table, finite timeouts, conditional idempotent put |
| `be-document-processing/src/document_processing/audit/audit_queries.py` | Bounded document Query and scope-bound continuation handling |
| `be-document-processing/src/document_processing/config.py` | Optional audit table/enablement and timeout settings |
| `be-document-processing/template.yaml` | Separate audit table, environment settings, minimal table-scoped IAM |
| `be-document-processing/tests/test_monitor_audit_storage.py` | Preserve existing tests and cover config, timeout, and token scope gaps |
| `plans/checkpoints/task-f3b580a5-dee4-45bf-b918-a5165c12f40c.red-green-proof.md` | Fresh valid follow-up proof, preserving historical parent evidence |

## Progress

- [x] Read original plan, acceptance findings, existing tests/config/template, scope reference, and relevant learnings.
- [x] Identify existing test work and invalid historical setup failure; define narrow implementation and proof plan.
- [ ] Implement audit modules and SAM configuration using valid focused TDD evidence.
- [ ] Run focused tests, template validation, and registered project gate.
