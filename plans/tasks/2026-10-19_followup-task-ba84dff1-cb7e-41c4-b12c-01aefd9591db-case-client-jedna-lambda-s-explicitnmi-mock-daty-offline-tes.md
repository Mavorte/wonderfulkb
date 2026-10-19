# Case & Client: verify existing implementation after operator waiver

## Operator scope override — 2026-10-19 14:29 Europe/Prague
Michal explicitly cancelled the TDD requirement for task-ba84dff1-cb7e-41c4-b12c-01aefd9591db (message1561717880481910827). This supersedes the inherited required_tdd_proof_missing finding and any historical task/plan instruction demanding behavioral RED, importable-stub RED, RED/GREEN proof or retrospective proof reconstruction. Do not fabricate, reconstruct or require RED. Preserve existing historical evidence unchanged. This waiver does NOT assert that the historical proof was valid.

tdd: skip

## Goal
Verify the existing Case & Client single-Lambda implementation with explicit mock data, offline tests and minimal SAM packaging. Parent task-task reference: task-8e06a0bb-7a44-449d-90f5-b7f22b9fc99a. Implementation is preserved; do not redo completed work. The prior follow-up existed solely for the now-waived proof finding.

## Deliverable
Evidence-only follow-up. Inspect the existing implementation against the original functional requirements in plans/tasks/2026-10-19_case-client-lambda-mock.md and existing original plan plans/2026-10-19_task-8e06a0bb-7a44-449d-90f5-b7f22b9fc99a_case-client-jedna-lambda-s-explicitn-mi-mock-daty-offline.md; their historical TDD requirements are explicitly superseded by this override. Record current offline test results and concise functional verification. If a real implementation defect is found, report precise evidence; only the minimal justified correction with regression tests is in scope. Production edits are otherwise forbidden.

## Testing
Retain normal functional/regression tests, registered project gate and independent acceptance. Do not disable or weaken assertions. No mandatory RED/GREEN proof. The canonical plan must explicitly include `tdd: skip` and `## TDD` followed by `N/A — explicitly waived by Michal 2026-10-19; ordinary tests remain required.` so runtime detection records no proof requirement. Missing SAM tooling or another verification blocker must be reported accurately, not called successful. No AWS deployment/cloud smoke, service/config/credential changes, live messages or provider operations. Stay in this repository; preserve ancestry and existing artifacts.
