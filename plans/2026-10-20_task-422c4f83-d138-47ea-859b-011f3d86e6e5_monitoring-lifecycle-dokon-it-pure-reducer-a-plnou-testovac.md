# Plan 2026-10-20: Monitoring lifecycle pure reducer and complete test matrix

Implement a bounded, in-memory lifecycle summary reducer that preserves event evidence and uncertainty within one caller-supplied window.

## Analysis
- The focused test imports `document_processing.audit.audit_lifecycle_observations`; the production module is missing.
- Existing tests cover an empty window, retry/partial publication, terminal-only run, conflicting run terminals, and duplicate identity. Extend this same focused file.
- Event contract: `plans/tasks/2026-10-20_monitor-mvp-22-retry-terminal-events.md`; host review: `plans/checkpoints/task-1e8311a4-08b0-4142-9bf9-6553815e572e.host-review.md` (historical evidence only; do not relabel the old proof).
- Relevant rules: bounded lifecycle summaries preserve uncertainty; do not invent runtime identity/evidence; use `be-document-processing/.venv/bin/python` for project pytest. No relevant PlantUML diagram was located.

## Approach
- Implement a pure reducer over the provided finite `Sequence[Mapping[str, object]]`; do not import event classes, query storage, iterate pages, or infer a globally latest run.
- Keep observations distinct by event identity, aggregate evidence by explicit run/attempt/publication scope, and expose ambiguity/unknown when ordering or relationships cannot be proven.
- Preserve the caller token by identity, always report partial coverage, and represent availability as not_configured, not_instrumented, unknown, or source failure only when supported by explicit evidence.

## TDD
**Test file:** `be-document-processing/tests/test_monitor_lifecycle_observations.py`  
**Run command (from repository root):** `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_lifecycle_observations.py`

First verify the project interpreter and imports/dependencies before capturing proof. Add the failing assertions to the existing test file, run exactly the command above for RED, then implement the reducer and rerun the identical command for GREEN. Capture proof under this task ID in `plans/checkpoints/`; use the TDD skill only through its permitted interface. Interpreter, dependency, conftest-import, or proof-permission failures are blockers, not genuine RED; preserve prior artifacts and do not reuse the original task ID.

```python
# Append a focused case using the existing event() helper and lifecycle import.
def test_orphan_attempt_and_terminal_only_attempt_remain_observed():
    result = lifecycle.reduce_observations([
        event("s", "AttemptStarted", 2, run_id="r", attempt_id="a", attempt_number=1),
        event("t", "AttemptFinished", 3, run_id="r", attempt_id="a", attempt_status="failed"),
    ], next_token=None)
    assert len(result.attempts) == 1  # RED: reducer module/contract is incomplete
    assert {e.event_id for e in result.attempts[0].evidence} == {"s", "t"}
```

| RED/GREEN case | RED | GREEN |
|---|---|---|
| Orphan and terminal-only attempt/run | missing behavior fails focused assertion | observed facts retained; no synthetic starts |
| Multiple runs/attempts and duplicate identity | missing scope/dedupe assertion fails | distinct runs preserved; exact duplicate counted once |
| Reordered/late fragments and conflicting terminals | missing uncertainty assertion fails | unknown/ambiguous with partial evidence; no timestamp/sequence latest choice |
| Explicit result/evidence scope and availability | missing scope/status assertion fails | scoped results and distinct availability/read-failure outcomes |
| Empty window, opaque token, no I/O | missing contract assertion fails | partial empty summary, identical token, reducer does no query/loop |

Implement the RED/GREEN cycle as directed by `skill:tdd`.

## Implementation
1. Confirm interpreter, imports, and dependencies before capturing proof; inspect the current focused tests and event mapping contracts.
2. Extend the focused test matrix with orphan/terminal-only attempts, multiple runs/attempts, duplicates, reorder/late fragments, conflicting terminals, explicit result scope, availability states, and no-I/O behavior.
3. Capture genuine RED with the exact focused command; then implement only the domain reducer module.
4. Run focused GREEN, relevant `be-document-processing` pytest, then registered gates `npm --prefix apps/backoffice test` and `npm --prefix apps/backoffice run build`; distinguish unrelated collection failures exactly and do not exclude tests or weaken assertions. Runtime caller tests, if relevant, use the project interpreter and Moto/fixtures only.
5. Preserve existing ownership and unrelated changes; no router, query, event/store, caller, dependency, deployment, or live provider changes.

## Files
| Path | Change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py` | Add pure, finite-window lifecycle reducer and summary types. |
| `be-document-processing/tests/test_monitor_lifecycle_observations.py` | Extend focused table-driven behavioral matrix. |
| `plans/checkpoints/task-422c4f83-d138-47ea-859b-011f3d86e6e5.red-green-proof.md` | Capture this task’s RED/GREEN evidence if authorized. |
| `plans/2026-10-20_task-422c4f83-d138-47ea-859b-011f3d86e6e5_monitoring-lifecycle-dokon-it-pure-reducer-a-plnou-testovac.md` | Maintain this plan. |

## Testing
- Focused RED/GREEN: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_lifecycle_observations.py` (identical argv).
- Relevant package suite: run `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/` and report collection failures separately from focused behavior.
- Registered gates: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- Assert fixed content-free event mappings, evidence event_id/sequence, unchanged opaque token, partial coverage, absence of synthetic pending/latest/durations/pages, and no reducer I/O.

## Progress
- [x] Canonical plan path obtained and existing source/test/contracts/learnings inspected.
- [x] Scope, TDD command, and verification gates recorded.
- [ ] Implementation and proof belong to the implementation task; no implementation performed in this planning run.
