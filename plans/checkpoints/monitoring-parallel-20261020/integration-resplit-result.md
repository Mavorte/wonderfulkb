# Integration branches resplit — user1561976018103832598

Supersedes the previous single 13-root HTTP lane and the blanket prerequisite that every core/helper root finish before any HTTP work. Actual technical readiness is branch-specific; ordinary sequential pauses, no invented manual gates.

## Verified branches
- HTTP base: 03 document events, 04 upload smoke, 07 run events, 09 attempts. Active; head9d34c790 dispatched planning warm-fork-9205/PID53321. Existing FileReceived read_document/store source available; first task establishes actual trusted auth/document seam and composition. Missing trusted case auth remains a real reportable blocker, not permission to infer claims from API key.
- HTTP steps:11→17→19→21 (source validation, extraction, signatures, publication). Four roots inactive/default-paused. Own processing_monitor_step_routes.py; only requires usable shared HTTP seam and relevant event contracts, not unrelated pages/lifecycle work.
- HTTP pages:13→15. Two roots inactive/default-paused. Own processing_monitor_page_routes.py; requires usable shared HTTP seam, page-event and pure mapper contracts, not all later core roots.
- HTTP lifecycle:24. One root inactive/default-paused. Own processing_monitor_lifecycle_routes.py; requires usable shared HTTP seam and actual reducer/event input contract.
- Worker integration:26→27. Two roots inactive/default-paused. Requires actual authoritative runtime-producer-context-contract.md/claim identity and actual relevant listener event seams. That runtime contract absent at inspection; no fake identity. Final27 requires real producer→read path.

Host owns subsequent readiness, shared-file edit and rollout serialization; workers do not query lifecycle or wait on task IDs. All read tasks retain their own install/deploy/live feature proof. No global all-core-complete gate. No parallel rollout to same service; revision guards and source/artifact provenance mandatory. No application code changed by host: backlog briefs only, originals saved before edits. No task duplicated, nine public moves performed, all thirteen member IDs/order verified; operations in integration-resplit-operations.jsonl.

## Collision answer
Shared checkout is not isolated worktrees. Concurrent edits may fail exact patches, overwrite another agent's work, or create a mixed-source passing/failing test result; a merge conflict is not guaranteed. Shared deployment can supersede the image under another smoke run. Existing acceptance/testing may detect concrete issues and produce a same-slot followup, but neither detection nor automatic repair is guaranteed; preserve gates and do not count collision as success. Core9681bd1b now failed acceptance infrastructure incomplete_diff_visibility; preserve outcome, no manual reopening or green relabeling in this split.
