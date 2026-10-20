# Plan 2026-10-20: Link historical cache-reuse TDD evidence

Produce only the missing task-scoped acceptance provenance for the completed cache-reuse characterization; retain all parent implementation and evidence unchanged.

## Analysis

- Parent `task-9e2461c6-3177-46d8-b83d-876682e528d3` completed the cache-reuse test matrix (focused 30, backend 222, backoffice 17 plus build) but its checkpoint says proof capture rejected a false new RED.
- The genuine historical RED/GREEN is in `be-document-processing/plans/checkpoints/task-73ee7806-e314-4dbf-9474-8b1228b9be04.red-green-proof.md`; RED found persisted `artifact_ids` list-vs-tuple mismatch, and GREEN verified the correction.
- The only acceptance finding is missing task-scoped TDD provenance. Do not modify production code, tests, parent proof, historical checkpoint, or manufacture a fresh RED.
- Relevant learning `learnings/test-failures/audit-characterization-no-false-red.md`: preserve genuine failing output and do not hand-write proof output when behavior already passes.

## Approach

- Inspect the `tdd` proof contract and helper to determine whether it supports an auditable follow-up artifact that references the parent proof and captures this task’s fresh GREEN.
- Verify the historical RED artifact’s exact task ID, command, failure assertion and matching recorded GREEN before linking it.
- Run the registered backend focused test command and the registry gate; preserve exact fresh outputs and command provenance.
- Use the supported proof workflow to create a task-scoped provenance artifact linking the historical RED and recording fresh GREEN. If the helper cannot represent linked historical evidence, record the limitation and leave acceptance unresolved rather than fabricating proof.

## Implementation

1. Read `tdd` instructions and inspect the proof-capture helper’s supported historical-link/provenance interface.
2. Confirm no newer code/test changes have invalidated the parent RED/GREEN applicability; do not redo completed matrix work.
3. Run `cd be-document-processing && .venv/bin/python -m pytest tests/test_monitor_cache_reused_events.py` and record the result.
4. Run the registered gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` and record the result.
5. Create only the supported task-scoped evidence artifact, citing parent task `task-73ee7806-e314-4dbf-9474-8b1228b9be04` and exact proof path; never reconstruct its output manually.

## Testing

- Focused fresh GREEN: `cd be-document-processing && .venv/bin/python -m pytest tests/test_monitor_cache_reused_events.py`.
- Registered gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- Check that the resulting artifact is scoped to `task-3fa192e3-bfa9-4298-a36b-30f1cb1c15ef`, cites the immutable genuine parent RED, and contains captured current GREEN evidence.

## TDD: skip

Evidence-only follow-up: existing implementation is already green, so a new RED would be false. Reuse the genuine parent RED and capture fresh GREEN only through the supported provenance workflow.

## Files

| Path | Action |
|---|---|
| `be-document-processing/plans/checkpoints/task-73ee7806-e314-4dbf-9474-8b1228b9be04.red-green-proof.md` | Read-only source of genuine historical RED/GREEN provenance |
| `plans/checkpoints/task-3fa192e3-bfa9-4298-a36b-30f1cb1c15ef.red-green-proof.md` | Create only if supported proof tooling can produce valid linked provenance |

## Progress

- [x] Resolve canonical plan path and inspect parent plan, checkpoints, genuine proof and learning.
- [ ] Inspect proof tooling contract and establish whether linked historical RED plus fresh GREEN is supported.
- [ ] Capture fresh verification and produce valid task-scoped provenance, or document the tooling blocker without fabricating evidence.
