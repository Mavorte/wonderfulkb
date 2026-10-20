# Plan 2026-10-20: Lifecycle canonical attempt ordinal repair

## Analysis

- The previous task already added unscoped terminal evidence, conflict preservation, and contradiction coverage. Keep those changes intact.
- The remaining defect is confined to ordinal selection in `audit_lifecycle_observations.py`: `AttemptStarted` uses integer `attempt_number` when `attempt_no` is absent; terminal events use both `attempt_number` and `attempt_id` fallback paths.
- Canonical attempt identity is `run_id` plus validated positive integer `attempt_no`. Alias-only or malformed evidence must not establish a definite attempt; preserve any existing unscoped/evidence behavior.
- Relevant context: original plan `plans/2026-10-20_task-59a2a44c-6136-465a-b2a7-2be7a6a6911a_monitoring-lifecycle-zachovat-unscoped-evidence-a-odm-tnout.md`; learning `learnings/architecture/2026-10-20_lifecycle-reducer-canonical-attempt-identity-followup.md`.

## Approach

- Remove fallback lookup of legacy `attempt_number` and inferred `attempt_id` ordinal for AttemptFinished/AttemptFailed.
- For AttemptStarted, only a positive integer canonical `attempt_no` assigns an attempt; supplied malformed or contradictory ordinal values continue to prevent definite selection.
- Keep legacy lookup state only if another supported reducer behavior depends on it; otherwise remove its construction as dead code.
- Add focused regressions showing alias-only AttemptStarted and AttemptFinished do not yield certain attempts, while canonical `attempt_no` and unscoped evidence semantics remain unchanged.

## Implementation

1. Extend `tests/test_monitor_lifecycle_observations.py` with RED assertions for alias-only `AttemptStarted` and `AttemptFinished` inputs.
2. Update ordinal selection branches to require validated canonical `attempt_no`; never translate `attempt_number` or `attempt_id` into an ordinal.
3. Run the focused lifecycle tests and the backend suite; run the registered backoffice tests/build gate and report results separately.
4. Reuse the genuine parent RED provenance where relevant; capture fresh GREEN verification for this follow-up task without fabricating a new historical RED.

## Testing

- Focused: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_lifecycle_observations.py`
- Backend regression: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests`
- Registered project gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`
- Assert that alias-only inputs yield no definite attempt; assert canonical attempt_no continues to group correctly and existing unscoped/conflict tests pass.

## TDD

**Test file:** `be-document-processing/tests/test_monitor_lifecycle_observations.py`  
**Framework:** pytest  
**Run command:** `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_lifecycle_observations.py`

Append the following tests before changing the reducer. These are focused follow-up regressions; cite the parent's genuine RED proof rather than claiming this codebase is still in its original RED state.

```python
def test_started_legacy_attempt_number_does_not_establish_attempt_ordinal():
    started = event("s", "AttemptStarted", 2, run_id="r", attempt_number=1)
    result = lifecycle.reduce_observations([started], next_token=None)
    assert result.attempts == ()  # RED: alias-only input currently establishes attempt 1


def test_finished_legacy_attempt_number_does_not_establish_attempt_ordinal():
    finished = event("f", "AttemptFinished", 3, run_id="r", attempt_number=1,
                     attempt_status="failed")
    result = lifecycle.reduce_observations([finished], next_token=None)
    assert result.attempts == ()  # RED: alias-only terminal currently establishes attempt 1
```

| Test | RED | GREEN |
|---|---|---|
| Alias-only AttemptStarted | Produces definite attempt | No definite attempt summary |
| Alias-only AttemptFinished | Produces definite terminal attempt | No definite attempt summary |
| Existing canonical/unscoped cases | Existing behavior remains characterized | Canonical grouping and unscoped evidence still pass |

Implement the focused cycle using `tdd`; do not fabricate RED evidence after the prior implementation already exists.

## Files

| File | Change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py` | Remove alias and inferred-ID ordinal fallback; require canonical positive `attempt_no`. |
| `be-document-processing/tests/test_monitor_lifecycle_observations.py` | Add alias-only start/terminal regression coverage, preserving existing tests. |

## Progress

- [x] Inspect existing reducer, focused tests, original plan, and relevant learnings.
- [x] Identify exact fallback branches and narrow repair scope.
- [ ] Add focused regression tests, remove fallback behavior, and verify all required gates.
