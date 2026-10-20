# Plan: Monitoring MVP — FileReceived audit store

## Analysis

- Keep this slice inside the `be-document-processing` package: persist and read the FileReceived envelope only; do not add upload hooks, HTTP, deployment, run projections, revision/fencing, or TTL.
- Follow `plans/monitoring/mvp-reference-20261019.md` (“Minimum společné prvním taskům”): separate audit table, conditional idempotent put, document-partition bounded Query and scope-bound continuation; errors remain errors.
- Existing package uses pytest and Moto (`be-document-processing/tests/test_aws_storage.py`); AWS adapters use boto3. `config.py` loads optional service settings from environment, and the package is installed via `pyproject.toml`.
- No PlantUML diagram was found for this slice. Relevant learning: `learnings/architecture/2026-10-19_monitoring-filereceived-audit-store-scope.md` reinforces exact envelope scope and distinguishing mock state from adapter semantics.

## Approach

- Define only `schema_version`, `event_id`, `case_id`, `document_id`, `sequence`, `type`, and `occurred_at`; do not persist `run_id`, business payload, or any other timestamp.
- Store each event in `wonderfulkb-uw-document-processing-audit`, partitioned by document and keyed by stable event identity. Conditional put preserves the first stored item on duplicates.
- Provide a small write/read interface. Query by document with caller limit and an opaque continuation bound to that document/query scope; never Scan. An unconfigured store is explicitly disabled; finite SDK timeouts apply; read failures propagate.
- Keep any table/IAM additions within existing templates and avoid changing business tables or package APIs.

## Implementation

1. Add focused tests first in `be-document-processing/tests/test_monitor_audit_storage.py`; establish RED against the planned audit API.
2. Add the three narrowly scoped modules `audit/audit_events.py`, `audit/audit_storage.py`, and `audit/audit_queries.py`; implement envelope validation, conditional put, bounded Query, and scope-bound continuation.
3. Add only required audit table/resource and IAM configuration to existing templates; add optional audit settings with explicit disabled behavior and finite SDK timeout.
4. Run the focused audit tests, then the registered project gate. Do not add or run producer/API/deployment work.

## Testing

- Verify put→read returns the same event identity and fields; duplicate put leaves exactly one unchanged event.
- Verify different document partitions are isolated, and two-page retrieval follows the continuation token without exceeding the requested limit.
- Make the adapter issue DynamoDB `Query` (not `Scan`); verify a read exception is surfaced, never converted to an empty success.
- Registered gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.

## TDD

**Test file:** `be-document-processing/tests/test_monitor_audit_storage.py`  
**Framework:** pytest; use Moto or focused fake DynamoDB responses.  
**Run command:** `pytest -q be-document-processing/tests/test_monitor_audit_storage.py`  
**Edit hint:** NEW FILE.

Start with this contract skeleton; adjust import names only to match the implemented small API while retaining each assertion:

```python
from document_processing.audit.audit_events import FileReceived
from document_processing.audit.audit_storage import AuditStore


def test_put_then_read_returns_same_file_received_event(audit_table):
    store = AuditStore(audit_table)
    event = FileReceived(
        schema_version=1, event_id="evt-1", case_id="case-1",
        document_id="doc-1", sequence=1, type="FileReceived",
        occurred_at="2026-10-19T12:00:00Z",
    )
    store.put(event)
    page = store.read_document("case-1", "doc-1", limit=1)
    assert page.items == [event]
```

| Test | RED | GREEN |
|---|---|---|
| put then read same event | Missing audit API or returned items differ | Read yields the identical event envelope |
| duplicate event ID | Duplicate is inserted or overwrites stored value | One unchanged stored event |
| separate documents | Query leaks another document’s event | Each document returns only its own event |
| bounded pagination | Missing/invalid continuation or extra items | Two pages continue within the requested limit and scope |
| read failure and query operation | Error is swallowed, or implementation scans | Error propagates and only Query is called |

Implementace TDD cyklu dle skill:tdd; capture focused RED/GREEN evidence before the registered gate.

## Files

| Path | Planned change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_events.py` | FileReceived schema and stable identity validation |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Conditional idempotent write and audit store configuration/timeout |
| `be-document-processing/src/document_processing/audit/audit_queries.py` | Bounded document Query and scope-bound continuation |
| `be-document-processing/tests/test_monitor_audit_storage.py` | Focused persistence, duplicate, scope, paging, error, and Query-not-Scan tests |
| Existing infrastructure templates only | Required audit table and least-necessary IAM configuration |

## Progress

- [x] Read the MVP reference, package adapter/test patterns, and relevant learning.
- [x] Fix the implementation boundary and focused verification plan.
- [ ] Implement the audit store using TDD.
- [ ] Run focused pytest and registered project gate.
