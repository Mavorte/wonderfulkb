# Lifecycle reducer independent completion review (2026-10-20)

## Verdict: MISSING

The focused test command passes (12 passed), but the implementation still violates required event-contract and ambiguity/availability requirements. This is a read-only review: no source, tests, task state, or prior proof/history changed.

## Evidence / probes

Command from repo root:

```text
be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_lifecycle_observations.py
12 passed, 6 warnings in 0.01s
```

Read-only contract check: `be-document-processing/src/document_processing/audit/audit_events.py:315-374`. `AttemptFinished.to_item()` emits `run_id`, `attempt_no`, `attempt_status`; `RunFinished.to_item()` emits `run_id`, `run_status`, optional `attempt_no`. `RunFinished` has `run_status`, not a generic finished state. The reducer's current `_RUN_TERMINALS` handling does not read that field. Pure synthetic probes (explicit `PYTHONPATH=be-document-processing/src`):

| Probe | Observed result | Required review |
|---|---|---|
| `AttemptFinished(run_id='r', attempt_no=1, attempt_status='completed')` | one attempt, state `completed`, run unknown | Passes canonical grouping/status. |
| `RunFinished(run_id='r', run_status='failed')` | run `finished` | Fails canonical run outcome: should retain/reflect `run_status`, not erase failed. |
| AttemptFinished with unknown status | attempt `unknown` | Fails invalid-vs-unknown distinction: contract says input consists of validated events; invalid status should not be silently treated as absent terminal. |
| AttemptFinished with no run_id | attempt `(None, 1, failed)` | Missing scope is represented as a definite failed attempt, not unknown/ambiguous with scope evidence. |
| Same `(event_id, sequence)`, payload failed then completed | only first retained, state failed | Conflicting same-identity payload gets silently discarded, making result input-order dependent rather than ambiguous with both facts preserved. |
| Same run/attempt id with attempt_no 1 then 2 | two separate attempts, second failed | No conflict/uncertainty surfaced for inconsistent identity-number scope; implementation splits claims. |
| `availability='not_configured'` passed bare | accepted as not_configured | No evidence parameter/validation; cannot establish “real configuration” evidence. |
| `availability='read_failure'` | raises ValueError | No explicit read-failure path/error marker in summary (source failure must propagate to caller for HTTP 503 mapping). |
| RunFinished with attempt_no | synthesizes attempt with unknown state | Run terminal attribution is not an attempt terminal/start; terminal-only must not create a claim of an attempt. |

Other observed implementation details: reducer line 84 builds a dict comprehension so first/last conflicting number can be overwritten; lines 93-99 group by `(run_id, attempt_no-or-id)` and permit `run_id=None`; lines 105-108 mark run finished/failed from event *type* and ignore canonical `run_status`; lines 113-126 silently ignore unrecognized status and retain legacy generic AttemptFinished behavior; lines 134-135 validate only enum strings, not evidence. Summary scope (line 136) is generic, not a representation of evaluated window/scope evidence; evidence stores only event id/sequence/type. Dedupes at lines 65-75 key solely on id+sequence and drops conflicting payloads.

The source event serializer defines `RUN_STATUSES`/`ATTEMPT_STATUSES` (audit_events.py:294-298), so valid run status domain is completed/partial/failed. This review does not propose a new event contract or impose additional status aliases.

## Minimal repair requirements (within original ownership only)

1. Run reducer must interpret canonical `RunFinished.run_status`; do not equate every RunFinished event with successful finished. Preserve exact status distinction or the original scope's explicit unknown/ambiguous mapping, with evidence.
2. Keep attempt grouping on canonical `(run_id, attempt_no)` while detecting contradictory identity/scope/number fragments; missing run scope and invalid status must not become definite per-attempt facts. Preserve partial evidence and surface uncertainty rather than silently split, overwrite, or pick one fragment.
3. Deduplicate only equivalent observations; same identity with inconsistent payload must remain represented as ambiguous/conflicting evidence, independent of input order. Reordered/late evidence remains bounded; never infer absolute latest.
4. Availability `not_configured`/`not_instrumented` needs explicit caller evidence according to original constraints, not a bare string. Preserve `unknown` on absence. Read failure must be expressible as an error for HTTP owner mapping, not mislabeled as empty success (the pure reducer itself must remain no-I/O).
5. Do not synthesize attempt entries from RunFinished's optional attempt_no. Keep run, attempt, and published-result observations distinct; terminal-only attempt remains observable but cannot imply start or whole-history completion.
6. Expand focused tests to lock these edge cases, while retaining the already passing twelve cases and the task's historical proof/infra record untouched.

No full suite, live/provider work, deployment, installation, or edits to source/tests were performed. This evidence file is the only change.