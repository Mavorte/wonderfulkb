# Run-events evidence: task-1d77ce99-3b09-48f7-9978-e0e99783c9b5

## Status (in progress)
SOURCE implemented; INSTALLED verified; DEPLOYED pending; LIVE-FUNCTION-VERIFIED pending.
Authoritative plan unchanged. Canonical proof records accepted behavioral RED404 and GREEN29 tests with identical focused argv. No manufactured proof or historical evidence replacement.

## Local verification
- Focused: `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_routes.py -k run_events` through tdd proof-capture red/green. RED run66b9726a4d424035a60dbe1d95959750 child1; GREEN682bbe0b37c44f1b830c9d6f8e6f27d6 child0.
- `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests`:185 passed,4 extraction/steps failures. Package command chained with && did not run on this invocation.
- `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests`:244 passed.
- `PYTHONPATH=be-validator-agent/trigger:be-validator-agent/pipeline be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests be-validator-agent/trigger/tests be-validator-agent/pipeline/tests`:621 passed,4 extraction/steps failures,1 skipped. These are sibling extraction implementation failures, not run-events; no ignores added.
- `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`:21 passed, bundled7 functions.
- `git diff --check`:pass.

## Installed artifact
Root build `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:task-1d77ce99 .` succeeded, installed wheel1.0.0 SHA256 `00ff410534211c144fbb57d7c456eb4ec4f3fdfd7b8f4b1bb671369615215bc5`. Initial index20ff83d07adb103e318d5d26f8710f350c39e8348b81047820bf42090834f329 retained.

Initial image smoke failed stale assertion excluding cache artifact_ids; the sole YAML and already-present DTO include artifact_ids. Assertion aligned to existing contract. Concurrent extraction owner changed shared source/smoke; preserved and rebuilt final candidate.

`docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:task-1d77ce99-final .` succeeded.
- Final index `sha256:e462d804b114d426df9d61e1b686f29afc07859ddd5ab3133dadb259585f9b8a`.
- amd64 manifest `sha256:99f39a86c78d8dbf6582d4accf082aa0f92af069fae29795d56a2c78154ad856`.
- config `sha256:260e97aa9897c948214044d2b2c3b40ada3063d62ab6dcc5b404c88e8ea7c7ef`.
- Aggregate source hash including untracked source: `be3c885329475e05d3dfbafaafa733fea8246fd1c35529ccc54ed72e94fb751f` (`git ls-files -z --cached --others --exclude-standard be-intake/app be-document-processing/src be-document-processing/pyproject.toml be-document-processing/requirements.txt | xargs -0 shasum -a 256 | shasum -a 256`).
- Installed run facade SHA256 `c9adeaa02bcf382ebb087b0153f09bbf76c372910c475eb7c1684ebf0b9a2c64`; audit_queries `db56ce0be958a19185f4c044d179db3ecf78a7281589061cc5fa46589ae49304` unchanged.
- `docker run --rm --platform linux/amd64 --network none --mount type=bind,source=/Users/michal/Projects/wonderfulkb/be-intake/tests/image_processing_monitor_smoke.py,target=/tmp/image_processing_monitor_smoke.py,readonly --entrypoint python wonderfulkb-ingest:task-1d77ce99-final /tmp/image_processing_monitor_smoke.py`:PASS UID10001, installed package1.0.0; real ASGI route/filter/empty continuation/cross-run400/no-store; provider clients stubbed. Not live producer evidence.
- Existing Docker registry credentials successfully pushed unique tag `task-1d77ce99-e462d804` into existing ECR `wonderfulkb-ingest`; ECR DescribeImages verified matching index at2026-10-20T09:56:20.197Z. No credential output or new auth flow.

## AWS preflight and recovery
AWS MCP STS verified account609394381050, existing SSO ai-hackathon-TeamAdmin. Existing TEST target eu-central-1:
`arn:aws:apprunner:eu-central-1:609394381050:service/wonderfulkb-ingest/c9ef96fae3da4192abd7e8280d43ae6b`, HTTPS `vt9mavpjky.eu-central-1.awsapprunner.com`.
Baseline RUNNING, last successful operation224a177ab8d54226adf8c569aefca482 (09:03:44–09:14:33Z).

Recovery image `609394381050.dkr.ecr.eu-central-1.amazonaws.com/wonderfulkb-ingest@sha256:d6764bd1bfa64dc5c89c0ffd026984a3c6c89bbb7e5cf4eba9bfad8b96aa375b`, original tag host-frozen-20261020-1102. DescribeImages ACTIVE; `docker pull --platform linux/amd64` by exact digest succeeded and retains the original locally. No pruning.

Recoverable baseline configuration (references only, no secrets):
- ImageRepositoryType ECR; image tag host-frozen-20261020-1102; port8080.
- AutoDeploymentsEnabled false; access role wonderfulkb-apprunner-ecr-access.
- Instance Cpu512/Memory1024/role wonderfulkb-ingest-instance.
- Env AUDIT_TABLE_NAME=wonderfulkb-uw-document-processing-audit; CASES_TABLE=wonderfulkb-uw-cases; DOCS_TABLE=wonderfulkb-uw-documents; RAW_BUCKET=wonderfulkb-raw-document-storage.
- Both MONITOR_AUTH_SECRET_ARN and PROCESSING_MONITOR_AUTHORIZATION_SECRET_ARN reference `arn:aws:secretsmanager:eu-central-1:609394381050:secret:wonderfulkb/monitoring-synthetic-20261020-4Dojab`.
- RuntimeEnvironmentSecrets API_KEY reference `arn:aws:secretsmanager:eu-central-1:609394381050:secret:wonderfulkb/ingest-api-key-UY77Za`.
- Health HTTP /healthz interval10/timeout5/healthy1/unhealthy5; network DEFAULT egress/public ingress/IPV4; default autoscaling revision1. All preserved.
- Intended config diff: image identifier only. No IAM/env/auth/business changes.
- Local exclusive PID lease acquired with `shlock -p "$PPID" -f plans/monitoring/.intake-deployment.lock`. Service/operation/source comparison immediately before update is required; App Runner has no atomic revision parameter.

## Fixture/request ledger
Default writes/inference0, ceiling2 forward rollouts/1 rollback/20 live GET/10 fixture preflight reads; inherited business budgets are not reset.
- Exact membership GetItem reads2: granted host probe case9fbe90e5-c36d-4986-8b52-d6b53ccf5a6f/document monitor-host-probe-20261020 is absent; SYN-A01/document34fcd896-107a-583f-a406-6a8100cf8150 exists.
- Current policy version dee3153b-291e-48ac-83bd-ba89aa59a695 has exact synthetic document grants; credential secret discovered via Secrets Manager metadata, no raw secret in evidence.
- Forward rollouts0; rollback0; live HTTP0; business/audit writes0; inference0. ECR candidate push1 (not a rollout).

## Validation constraints
validate-implementation loaded, but its plan-compliance reference read was denied by filesystem policy; aws-containers ECR and signing-in-to-aws auxiliary references likewise denied. No alternate-path bypass. Manual plan/API/scope validation performed. No acceptance run manifest was supplied/discovered for this task; do not invent a finalized acceptance result.

## Forward rollout reservation
Reserved forward attempt1 before guarded UpdateService. Current intake suite after sibling fixes:200 passed. Candidate installed smoke passed. No live HTTP or business writes yet. Mutation must abort if baseline source, status, instance config, recovery digest, candidate digest or latest service operation differs from the preflight above. Only SourceConfiguration.ImageRepository.ImageIdentifier changes; configuration is copied from the freshly read service.

UpdateService guard passed at2026-10-20T09:59:05.849968Z. Operation `e5bcdf6b57c74901a5befeb9678f8add` accepted, status OPERATION_IN_PROGRESS. Requested image task-1d77ce99-e462d804 only. Rollout not yet attested complete. Forward rollouts1/2, rollback0/1, HTTP0/20, membership reads2/10, writes0/inference0.

## Continuation: fresh verification (20 October 2026)

Earlier entries above are historical and preserved. Current MCP signed STS confirms expected account/SSO role. DescribeService/ListOperations show the same candidate running and operation `e5bcdf6b57c74901a5befeb9678f8add` **SUCCEEDED**, started09:59:05Z, ended10:10:25Z. ECR DescribeImages at10:12:41Z confirms candidate index and recovery index above ACTIVE; candidate last pulled09:59:43.558Z. No new deployment submitted; env/auth/IAM/network/health configuration still matches baseline references.

Fresh focused command:29 passed. Attempt to capture fresh GREEN with current discovered helper failed prelaunch (`child_started=false`, historical proof format rejected); the old canonical genuine RED404/GREEN29 is preserved without manual edits. No production edits/new RED were necessary. Independent focused run passed. Broad exact PYTHONPATH gate:636 passed/1 skipped; backoffice exact test/build:21 passed/7 bundled; `git diff --check`:pass. Candidate `docker run` smoke passed, UID10001/package1.0.0, actual ASGI run-events filter/empty continuation/cross-run400/no-store, no network/provider calls. Current facade/reader/main/auth file hashes match installed image hashes. No fresh package rebuild is needed for unchanged task source.

Completed fixture preflight read3/10 returned no Item for exact wire-format SYN-A01/document34fcd896-107a-583f-a406-6a8100cf8150 GetItem (consistent, IDs-only projection). A diagnostic native-string-key call was rejected by SDK validation before any remote read; no result inferred. Worker GetFunctionConfiguration still has neither execution nor audit env; revision `ff5d8dde-9c6c-45eb-8b42-d05dfd700f64`, modified08:19:01Z. No producer rollout or synthetic write attempted.

Reserved **one** document-events HTTPS GET (1/20) for task-local `task-1d77ce99-http-check.py`, conditional on fresh profile STS/service/policy/active hash binding and exact grant checks. Secrets remain inside the process; endpoint from DescribeService, redirects disabled, output limited to statuses/IDs/assertions. This is scope/fixture discovery, not positive run-events proof. No fabricated run ID will be sent. No later shared evidence located for this task's operation/tag or HTTP usage; sibling ledger records retain zero live HTTP. Case Client allowance untouched.

## Actual HTTPS result and current delivery status

Executed `be-document-processing/.venv/bin/python plans/monitoring/task-1d77ce99-http-check.py` once. Fresh explicit local SDK session `ai-hackathon`/eu-central-1 signed STS matched609394381050; service RUNNING/candidate image assertion passed. At10:14:16.967535Z policy version `dee3153b-291e-48ac-83bd-ba89aa59a695` still had an active SERVICE hash binding for the runtime-retrieved token and the exact current SYN-A01/document grant. Neither credentials, credential hashes nor policy bodies were emitted/saved.

At10:14:17.233830Z authenticated HTTPS GET `/v1/cases/SYN-A01/processing/documents/34fcd896-107a-583f-a406-6a8100cf8150/events` on the freshly described existing service host returned **404**, `Cache-Control: private, no-store`. This agrees with the current consistent metadata GetItem returning no Item; the historical membership observation is not relabelled. The checker exits2 for this unmet prerequisite, not success. No event content was logged. No run ID was observed/invented; **no positive run-events HTTP request was possible**. No empty response or negative response is used as run-route functionality proof.

| Delivery state | Current evidence |
|---|---|
| SOURCE | Implemented; facade/shared reader/cursor/filter/auth/sole-YAML/README verified, 29 focused green; no additional source correction required in this continuation. |
| INSTALLED | Verified original built wheel/image again through network-none UID10001 ASGI smoke. Image inspect RepoDigests matches registry candidate index; linux/amd64. |
| DEPLOYED | Verified operation SUCCEEDED10:10:25Z, current RUNNING service image tag maps to candidate index `sha256:e462d804b114d426df9d61e1b686f29afc07859ddd5ab3133dadb259585f9b8a`; amd64 manifest `sha256:99f39a86c78d8dbf6582d4accf082aa0f92af069fae29795d56a2c78154ad856`. No duplicate update. |
| LIVE-FUNCTION-VERIFIED | **BLOCKED**. Exact currently-granted synthetic membership absent; document GET404, no genuine run/event IDs. Nonempty run filtering/DTO/continuation/parity remain unverified through actual live HTTP. |

Final cumulative task ledger: forward1/2; rollback0/1; HTTP1/20; direct completed fixture preflight reads3/10 (plus at most1 membership read inside HTTPS GET; conservatively4/10 including it). One rejected client-side parameter-validation diagnostic is not a completed remote read. Writes0, queue sends0, POST0, inference0, policy/IAM edits0. No additional ECR push/build/rollout in this continuation; previous installed artifacts retained. No outage or rollback triggered. No Case Client budget used.

### Exact same-delivery operator continuation for Jackie

1. Resolve the discrepancy between historical SYN-A01 membership and current absent exact metadata with the synthetic fixture owner. Establish a **currently existing, already permitted** metadata tuple with a genuine observed run/event and producer provenance, or a specifically supported/authorized zero-paid/no-downstream fixture path. This task does not authorize recreating metadata, seeding audit, widening grants, replaying the historical PDF, or queueing work. Current worker revision above lacks execution/audit env, so do not claim worker integration from this read image. Reuse native trigger readiness handoff if producer operator work is required.
2. Existing intake artifact is already deployed: target ARN above; candidate digest above; **no source/config diff or outstanding UpdateService command** is required for the run-events source. Recovery remains ACTIVE digest `d6764bd1bfa64dc5c89c0ffd026984a3c6c89bbb7e5cf4eba9bfad8b96aa375b` with baseline configuration references above. Any later mutation must reacquire owner guard and freshly compare operation/source/config; never overwrite a foreign revision.
3. After fixture prerequisites are actually established, resume this same delivery with remaining HTTP19/20 and at most6 conservative fixture reads; retrieve credentials in memory again and validate current policy/membership. Issue direct run-events GET for an **observed** run, assert nonempty known event ID/type/scope, sole YAML DTO, UTC/partial/no-store, other-run/FileReceived exclusion, continuation/cross-run400 where actual fixture permits, auth/scope negatives and document parity. Keep writes/inference0 unless a separately concrete supported path is authorized. Do not blindly rerun the checker and consume a reserved request again.

### Validation/review and proof readback

Manual scoped plan/API/security/architecture review: single facade and AuditStore; authorization/membership precede one bounded Query; cursor scope validated before audit I/O; no Scan/fill-page loop or new producer/business writes; safe DTO and shared503/no-store policy; existing route registrations/source preserved. Sole YAML run operation describes actual evaluated-window/partial/event-ID ordering and nullable continuation. Existing full schema gate passed. No new production defect identified.

`validate-implementation` loaded; exact `workflows/plan-compliance.md` read remains filesystem-denied. SDK configuration/DynamoDB auxiliary reference reads also denied; no alternate-tool/path bypass. Exact signing-in-to-aws reference is now readable and was followed. Canonical proof was read back after broad verification; original RED and GREEN sections/argv/output remain intact. Current helper incompatibility is reported, not manually repaired or reconstructed. No caller-supplied acceptance run manifest exists for this task; no acceptance success finalized. Review report is at `/Users/michal/.openclaw/workspace/plans/review/task-1d77ce99-3b09-48f7-9978-e0e99783c9b5.md`. Overall delivery remains incomplete on live-fixture prerequisite; no completion claim.

Final save-learning workflow: discovered `add-frontmatter.py` executed successfully with `--output learnings/runtime-errors/2026-10-20_run-events-rollout-needs-current-synthetic-membership.md`; actual helper confirmed saved. No authoritative plan modified.
