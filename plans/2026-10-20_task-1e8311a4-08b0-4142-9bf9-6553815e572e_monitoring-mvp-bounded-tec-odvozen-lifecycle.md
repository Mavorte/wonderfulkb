# Plan 2026-10-20: Monitoring MVP: bounded čtecí odvození lifecycle

Pure in-memory reducer for one caller-bounded window of validated audit observations; preserve uncertainty and event evidence.

## Progress

- [x] Resolve canonical plan path
- [x] Research existing contracts and patterns
- [x] Incorporate relevant learnings
- [x] Finalize implementation and verification steps

## Analysis

### Context
- The reducer consumes only an already-limited `Sequence[Mapping[str, object]]` and opaque `next_token`; no I/O, pagination, router wiring, or edits to `audit_queries.py`.
- Keep distinct observations and evidence (`event_id`/sequence); partial or conflicting context yields unknown/ambiguous rather than inferred chronology or a latest-state claim.
- `RunQueued` absence must not hide observed attempts/terminals. Retry enqueue and partial publication are non-terminal; conflict, lease loss, and silence do not close a run/attempt.
- Summary coverage remains partial; no durations, totals, percentages, synthetic pending attempts, implicit latest run, or empty-success interpretation of read failure.
- `audit_queries.read_document` already makes one bounded Query and returns `AuditPage(items, next_token)`; its ordering is technical identity order, not chronology or snapshot.
- Neighbor contracts in `plans/tasks/2026-10-20_monitor-mvp-22-retry-terminal-events.md` and `...-20-publication-events.md` permit terminal-only/reordered fragments; `RunFinished` may lack attempt scope, while `ResultPublished` is not a run terminal.
- Existing audit tests use pytest under `be-document-processing/tests`; retain the reducer test isolated from Moto/AWS and literal event mapping fixtures.

### Relevant knowledge
- `learnings/architecture/2026-10-19_monitoring-filereceived-audit-plan-scope.md`: keep read scope bounded, propagate read failures, and do not expand permissions into projections or HTTP.
- `learnings/architecture/2026-10-20_audit-envelope-decimal-round-trip.md`: existing event items may be typed instances converted by caller; this reducer accepts validated mappings and must not relax or own event-envelope parsing.
- Recall search used local fallback (`wonderfulkb-learnings` collection unavailable); no critical-patterns file was returned.

## Approach

1. Inspect the audit package, existing focused test conventions, and event contract documents for `RunQueued`, `AttemptStarted`, retry/terminal events, and publication observations.
2. Use the prescribed TDD workflow: create focused table-driven tests with literal event mappings first, verify RED, then implement the pure reducer in the required module.
3. Model observation scope, partial coverage, unchanged `next_token`, run/attempt observation summaries, and published-result observations with evidence; represent ambiguous/incomplete associations explicitly.
4. Keep availability distinctions evidence-based: `not_configured` only from actual configuration, `not_instrumented` only from producer/capability evidence, otherwise unknown; source failure remains an error for the HTTP owner to map to 503.
5. Verify focused tests and registered backoffice tests/build; make no HTTP integration or deployment changes in this slice.

## Implementation

- Add the reducer to `be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py`; it must not import unimplemented event classes or invoke a reader/query.
- Cover start → retry → next attempt → run terminal; partial publication; terminal-only/max-attempt without invented claims; multiple runs/attempts; duplicate identity; reorder/late fragment/conflicting terminal; empty partial window; continuation token; availability/read-failure distinctions.
- Preserve existing AttemptStarted endpoint semantics and all existing endpoint/reducer behavior.

## Testing

- Query spy/fake confirms reducer performs no I/O, query calls, or window iteration.
- Focused matrix proves no synthesized execution list, terminal, complete coverage, pagination totals, or chronology claim.
- Run focused Python tests, then the registered gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.

## TDD

Implement with `skill:tdd`; first add `be-document-processing/tests/test_monitor_lifecycle_observations.py`, then capture RED and GREEN evidence in `plans/checkpoints/task-1e8311a4-08b0-4142-9bf9-6553815e572e.red-green-proof.md`. Test file follows existing pytest layout. Run only this test file from `be-document-processing` with `python -m pytest tests/test_monitor_lifecycle_observations.py` using the project environment.

```python
from document_processing.audit import audit_lifecycle_observations


def test_reducer_preserves_partial_scope_and_reader_token():
    result = audit_lifecycle_observations.reduce_observations([], next_token="opaque")
    assert result.coverage == "partial"  # RED: reducer module/function does not exist yet
    assert result.next_token == "opaque"
```

| RED test case | Expected RED | GREEN behavior |
|---|---|---|
| Start/retry/attempt/run terminal | Required reducer import/API absent (implementation-specific RED) | Partial evidence-backed observation summaries, retry does not close run |
| Partial publication and terminal-only | Required reducer cases absent | No invented run/attempt terminal or claim |
| Duplicate, reorder, late fragment, conflicting terminals | Required reducer cases absent | Preserve distinct evidence; ambiguous where order/scope cannot be proven |
| Empty window, continuation, availability and failure | Required reducer cases absent | Partial coverage, unchanged token, distinct unknown/configuration/instrumentation/error outcomes |

## Files

| Path | Change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py` | Add pure bounded-window lifecycle observation reducer |
| `be-document-processing/tests/test_monitor_lifecycle_observations.py` | Add focused literal-mapping table tests and no-I/O assertion |
| `plans/2026-10-20_task-1e8311a4-08b0-4142-9bf9-6553815e572e_monitoring-mvp-bounded-tec-odvozen-lifecycle.md` | Track implementation plan |
