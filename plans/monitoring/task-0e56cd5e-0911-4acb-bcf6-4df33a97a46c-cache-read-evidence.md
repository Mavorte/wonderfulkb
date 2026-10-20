# Cache observation read delivery — task-0e56cd5e-0911-4acb-bcf6-4df33a97a46c

## Historical delivery status (before continuation below)
- SOURCE: implemented; genuine helper-captured RED/GREEN, focused 12 passed.
- INSTALLED: editable package 1.0.0 installed; final amd64 intake image imports and failed-cache DTO verified under UID10001, network disabled, no source mounts.
- DEPLOYED: not yet. Current target still host-frozen image below.
- LIVE-FUNCTION-VERIFIED: not yet; no live HTTP requests made.

## Source boundary and baseline
Existing worktree is extensively modified, including untracked monitoring modules. Preserved other owners' changes. No authoritative plan was edited. Baseline SHA256 before production edits:

| File | SHA256 |
|---|---|
| processing_monitor_page_routes.py | d210c5ac69b74d7b61f1f8a8742f1dfc1921e11ba70d0f20da7ec3fbedc143ff |
| processing_monitor_step_routes.py | d4d1f68df6235659a272b264885fcc62266e3f2b45c5a52d0b69ed9996093152 |
| processing_monitor_routes.py | f1637f2d07556787c774dce296e520c545349bc7e9caeea7337c65bab0270775 |
| openapi-processing-monitor.yaml | 9d49f9e36dd72d4b7a8f7f40b607a6cdf61d6fae5bfebe76e9b4a9b921e610a6 |
| test_processing_monitor_page_routes.py | 09a7d00e972a4ba6825ffffbd49b08ec2aa6b165482d370fd6b7691ab8c48fc2 |

Reuse uses existing pure mapper/reader without modifications. Extended page allowlist and document-event opaque references; explicitly retained only executed page types in steps. Extended only pages operation/reuse DTO in sole YAML. Updated obsolete three-page-type contract test, preserving all executed-step branch assertions. Unknown cached fields omitted; no new completion, current inference, content or storage keys.

Recall helper: backend local, collection wonderfulkb-learnings, diagnostic Collection not found. Applied pure/window-scoped mapping, current auth/membership, operation-bound cursor and image import rules.

## Commands and actual outcomes
- Dependency imports succeeded before RED.
- `TASK_ID=task-0e56cd5e-0911-4acb-bcf6-4df33a97a46c python3 /Users/michal/.config/opencode/skills/tdd/scripts/proof-capture.py red -- be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_cache_reused.py`: accepted_red, child exit1, 5 failed/7 passed. Failures are reuse dropped from pages, not dependencies. Canonical RED read before production edits.
- Same helper/argv with `green`: accepted_green, child exit0, 12 passed. Proof: `plans/checkpoints/task-0e56cd5e-0911-4acb-bcf6-4df33a97a46c.red-green-proof.md`.
- `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests`: first run399 passed/1 failed, obsolete contract three-branch assertion; fixed that assertion to include reuse in pages only.
- `PYTHONPATH=be-validator-agent/trigger:be-validator-agent/pipeline be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests be-validator-agent/trigger/tests be-validator-agent/pipeline/tests`:592 passed/1 skipped/1 failed. Concurrent owner added `test_run_events_continue_across_unmatched_window`; actual run-events route returns404. This route was absent at initial source inspection and remains an explicit prerequisite, not implemented by this slice.
- `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`:21 passed, bundled7 functions, exit0.
- `be-document-processing/.venv/bin/python -m pip install --no-deps -e ./be-document-processing`:success,1.0.0; editable wheel SHA256 `242cc79a542c0a95480a6638c7b51df0c1b85d6712b75d62dd60896e09ae12ac`.
- `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:task-0e56cd5e .`:success. Installed noneditable wheel1.0.0 SHA256 `a0c56d65fc609cb1787ea58a4ea2b3625b136296831968c0a5678992e517dbcd`.
- Image index `sha256:c12c518669d14bf8e4519e8e81049bdf35904938a2117cd56a5f684ddd080afb`, amd64 manifest `sha256:b9426b2278ee04782d3d37cf4aadfc9e05261f6b777ccdcbe5c6a53f6264cbd6`, config `sha256:6cd4949c9450fd8045ef9d84f58cbbf0203baca2bf9814fd2a0b1f8d6caab10b`.
- First image DTO smoke failed due to smoke constructor omitting mandatory schema_version/type, not image imports. Corrected command passed: UID10001, installed `/usr/local/lib/python3.12/site-packages`, registered page router, failed cached_status preserved, no steps item. `docker run --rm --platform linux/amd64 --network none --entrypoint python wonderfulkb-ingest:task-0e56cd5e ...`, no bind mounts.
- `git diff --check`:exit0.

## Fresh AWS preflight and recovery
AWS MCP actual api_calls verified successful STS account609394381050 TeamAdmin session, App Runner ListServices/DescribeService/ListOperations/ListTagsForResource, ECR DescribeImages, DynamoDB DescribeTable and Secrets Manager DescribeSecret/GetSecretValue (contents never returned into evidence). No authentication denial. An attempted script import of hashlib was rejected by sandbox validation before any APIs; removed it rather than claiming a computed hash.

Target: `arn:aws:apprunner:eu-central-1:609394381050:service/wonderfulkb-ingest/c9ef96fae3da4192abd7e8280d43ae6b`, project tagwonderfulkb, RUNNING. Discovered URL `https://vt9mavpjky.eu-central-1.awsapprunner.com`. Last observed successful operation `224a177ab8d54226adf8c569aefca482`, start2026-10-20T09:03:44Z/end09:14:33Z. `UpdatedAt` remains creation-era and alone is not a revision guard.

Recovery image `609394381050.dkr.ecr.eu-central-1.amazonaws.com/wonderfulkb-ingest:host-frozen-20261020-1102`, ECR digest `sha256:d6764bd1bfa64dc5c89c0ffd026984a3c6c89bbb7e5cf4eba9bfad8b96aa375b`. Local exact digest is retained and import verified under UID10001/network none. AutoDeploymentsEnabled=false. No recovery tag overwritten, no pruning.

Current audit table `wonderfulkb-uw-document-processing-audit` ACTIVE, pk/sk keys. Both monitoring policy references point to existing synthetic-only secret. Current policy version `dee3153b-291e-48ac-83bd-ba89aa59a695`. Historical reports of missing table/policy no longer describe this preflight. API_KEY remains a runtime secret reference. No IAM/env/auth changes requested by this slice.

## Fixture preflight and ledger (in progress)
Server-owned active policy enumerates exact synthetic scopes:
- case `9fbe90e5-c36d-4986-8b52-d6b53ccf5a6f`, document `monitor-host-probe-20261020`: exact current membership absent, so not usable.
- case `SYN-A01`, document `34fcd896-107a-583f-a406-6a8100cf8150`: exact current metadata membership verified by strongly consistent GetItem projecting only IDs.

Initial two bounded audit queries mistakenly used CASE#... key encoding; these empty windows do NOT prove absence of observations. Canonical `document_key` is JSON-encoded `[case_id,document_id]`; correct bounded reads are required next. No Scan/history replay/content reads.

Task live budget: at most12 HTTP GET; consumed0. Uploads0, audit inserts0, business POST0, provider calls0, policy writes0, deployment0, rollback0. Exact fixture GetItem2 and mistaken bounded Query2 consumed. Case Client budgets untouched; inherited operator lock/budget reconciliation not yet established. Repository lock search found only Case Client execution lock; did not read or modify it.

## Open prerequisites
Actual run-events route absent: cannot prove pages/document/run identity parity without owner seam. Preserve owner concurrent failing test and do not add forbidden new route.
Need existing deployment owner serialization/budget reconciliation before mutation. Candidate artifact is ready locally, recovery import verified. Existing ECR credential helper binary absent; Docker's existing supported authentication/push capability not yet tested. Need nonempty reuse live fixture and same-task guarded rollout/live HTTP.
Skill `aws-containers` loaded; direct read of bundled ecr reference was denied by runtime filesystem permission. `validate-implementation` loaded; its plan-compliance workflow read also denied. Neither denial bypassed.

## Continuation: current source and runtime readback

The historical sections above are preserved. New checks supersede their status only where explicitly proven below.
- Current focused command:12 passed. Broad registered Python command:636 passed,1 skipped. Backoffice registered gate:21 passed/build bundled7 functions. `git diff --check`:pass.
- Historical canonical helper proof remains unchanged, genuine RED5 failed/7 passed → GREEN12 passed. No production gap found; no manufactured RED. task-evidence fetch succeeded but reports verification evidence:none for both available sessions; canonical proof remains the direct historical command/output source.
- Editable install1.0.0 succeeded, wheel SHA256 `e120eb51281248414f1845e8dc296c08f342d469796aec1522d3c3ad0c51b840`.
- Rebuilt candidate index `sha256:3a5e66b019e4a8af95fddd631cc857bcba4da65c29099472a1446106dfeef01b`; runnable amd64 manifest `sha256:99f39a86c78d8dbf6582d4accf082aa0f92af069fae29795d56a2c78154ad856`, config `sha256:260e97aa9897c948214044d2b2c3b40ada3063d62ab6dcc5b404c88e8ea7c7ef`.
- Source aggregate `be3c885329475e05d3dfbafaafa733fea8246fd1c35529ccc54ed72e94fb751f` exactly matches shared native owner build. Current deployed image is `task-1d77ce99-e462d804`, ECR index `sha256:e462d804b114d426df9d61e1b686f29afc07859ddd5ab3133dadb259585f9b8a`. SAME runnable manifest/config as rebuilt task source; only build attestation/index differs. Native owner rollout operation `e5bcdf6b57c74901a5befeb9678f8add` is now SUCCEEDED, started09:59:05Z/ended10:10:25Z, target RUNNING. No new rollout performed in this continuation; this is shared deployed artifact attribution, not a claim of this agent sending UpdateService.
- Pulled the exact current registry digest, retained locally, then ran the enhanced smoke against THAT digest as UID10001, `--network none`, stdin script, no source mounts. All direct completed/failed cache-pages, unknown model, opaque IDs, document/run identity, steps exclusion, attempt/run isolation and existing auth/cursor/read503 assertions passed. First added smoke assertion incorrectly included fixture-only filename in expected public DTO; corrected test expectation, no production code changed.
- Installed page route hash `dd26e30e006ac62dedaf2a9b6d26b5c4af2e95717273e5e5ec8b7aaace78b831`; mapper `f93174aeb1cf54255ff7a26d1f0b1a0ff79cb3b74d7b9dae82ff362a48f720d4`; reader `db56ce0be958a19185f4c044d179db3ecf78a7281589061cc5fa46589ae49304`. Installed package1.0.0 under site-packages.
- AWS signed STS verified expected account. DescribeService configuration retains old env/IAM/auth/health/auto-deployfalse; only owner image reference changed. Existing lock PID86998 is not running; no lock takeover or mutation attempted.
- Worker GetFunctionConfiguration still lacks both EXECUTION_TABLE and AUDIT_TABLE_NAME, revision `ff5d8dde-9c6c-45eb-8b42-d05dfd700f64`, LastModified08:19:01Z. Audit table ACTIVE pk/sk, no GSI. No migration/backfill/worker update in this read slice.
- Two fresh strongly consistent projected typed-key GetItem requests for approved SYN-A01/document34fcd896-107a-583f-a406-6a8100cf8150 returned no Item. This is a NEW membership blocker, unlike historical positive membership. One alternative native-key call was rejected by parameter validation (no successful read); it does not change the two empty results. No metadata write or membership fallback.
- Recall backend=local, collection=wonderfulkb-learnings, diagnostic Collection not found; read all3 returned learnings. Direct bundled ECR, SDK DynamoDB and validation workflow reads denied by filesystem policy; no bypass attempted. Access skill canonical reference was readable.

### HTTP reservation before execution
Own previous HTTP consumption0; no newer own-task requests found in monitoring evidence. Reserve GET1/12 for exact authorized document-events discovery on approved synthetic scope, with current runtime policy/hash/grant checked in memory. Current metadata preflight is absent, so expected404 is diagnostic ONLY, never cache feature proof. No invented run/attempt and no pages request without observation identity. Task-specific `task-0e56cd5e-0911-4acb-bcf6-4df33a97a46c-http-check.py` performs one request without redirects or response/content/header dumps. No writes permitted; no implicit retries or history fill loop.

### Executed HTTP outcome and final ledger
At `2026-10-20T10:15:51.922028+00:00`, the one reserved GET to discovered host `vt9mavpjky.eu-central-1.awsapprunner.com`, `/v1/cases/SYN-A01/processing/documents/34fcd896-107a-583f-a406-6a8100cf8150/events?limit=50`, returned **404**, Cache-Control **private, no-store**. In-memory signed profile STS, current service image, policy version `dee3153b-291e-48ac-83bd-ba89aa59a695`, token hash/state=active and exact case/document current grant all passed. No response body or credentials retained. This confirms diagnostic scope denial, NOT functional cache-pages success.

Total own task HTTP **1/12 consumed,11 remaining**; exact fixture GetItem4 successful calls total (2 historical positive +2 fresh absent); native-key diagnostic1 rejected before network; audit Query2 historical incorrectly keyed,0 new. Business POST/upload/queue/audit seed/provider/policy writes **0**. This continuation ECR push0/rollout0/rollback0; shared owner's prior successful rollout is attributed separately above. No Case Client budget touched.

Same cached package-builder stage wheel SHA256 `00ff410534211c144fbb57d7c456eb4ec4f3fdfd7b8f4b1bb671369615215bc5`, read directly from `/wheels` under network-none builder container; matches native owner's deployed package. Current verified recovery/config references preserved separately in `task-0e56cd5e-0911-4acb-bcf6-4df33a97a46c-current-recovery.json`; original historical recovery JSON untouched. Current exact ECR image retained locally and import/ASGI verified. No rollback needed or attempted.

### Current delivery state and same-task Jackie continuation
| State | Current evidence |
|---|---|
| SOURCE | Verified existing implementation, historical genuine TDD preserved; no new production gap. |
| INSTALLED | Reinstalled editable1.0.0 and rebuilt noneditable wheel/image; direct cache-pages artifact smoke passed. |
| DEPLOYED | Current shared native owner artifact matches source aggregate and exact runnable amd64 manifest/config; actual successful operation and RUNNING read back. No new UpdateService by this continuation. |
| LIVE-FUNCTION-VERIFIED | **BLOCKED**, not complete: approved synthetic membership is now absent and no trustworthy reuse run/attempt is available. |

Jackie must resolve the current membership/provenance discrepancy for existing SYN-A01/document34fcd896-107a-583f-a406-6a8100cf8150 through its actual metadata owner, without manual metadata/audit seed or grant widening, and supply an already-supported genuine reuse observation. Worker execution/audit env remains absent; new producer or physical schema integration is outside this read slice and cannot be faked. After a legitimate fixture is available, reverify current service/ECR digest/config and policy/membership, reserve from remaining11 GET, then read bounded document discovery → actual run pages with observed attempt → run events parity, relevant continuation and isolation/no-store checks. Do not run pages with invented IDs, scan/fill history, replay old documents or invoke providers. If owner delivers a different compatible artifact, acquire existing owner guard and compare current revision/config/operations before any mutation; use retained current recovery only against the owned revision. There is no missing read-image rollout command for the currently identical deployed artifact.

Plan-compliance validation: read projection/contract/TDD/boundedness/auth/no-store and registered local gates pass; mandatory positive live feature branch unmet. Canonical proof read back after broader verification, both RED and GREEN sections intact. Review report saved at canonical host review path with NEEDS_FIX, no new fix plan (caller forbids plan edits). Task remains **INCOMPLETE / operationally blocked**, not mark_complete. Remaining unmet verification belongs to this same delivery.

### Final concurrent-source guard
Final `git diff --check` passed, but the source aggregate changed to `62155dcfc67217010bb85ec53dc8185c598de80c02bb8a0a9a0456abca3f0050`: another owner updated `processing_monitor_step_routes.py` from installed hash `02623a55fb2b55c9dee2d337dd5a0350048b2a28dd1fb525bc13ef511e72bf28` to `49411e6d3b56805b6fa45ff1144abcdbdb771fa6be9f20a5318322134a27d8f8` (steps cursor size/duplicate-field handling). Preserved this source. All listed cache page/auth/facade/audit hashes remain identical to verified deployed image. Thus whole-source equivalence above is a **build-time snapshot**, not certification that this later sibling cursor change is deployed. No tag was rebuilt/pushed over that sibling change.

Because of this fresh change, ran `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_cache_reused.py be-intake/tests/test_processing_monitor_step_routes.py`: **40 passed**. Earlier full636/1skip is explicitly pre-drift; final cache/steps regression passes. Deployment attribution is limited to this task's unchanged cache-page implementation; the current image does not certify the later sibling steps cursor. Do not overwrite/relabel either artifact.
