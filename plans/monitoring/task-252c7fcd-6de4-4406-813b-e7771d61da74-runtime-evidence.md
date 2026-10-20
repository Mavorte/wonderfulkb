# Steps HTTP delivery evidence — task-252c7fcd-6de4-4406-813b-e7771d61da74

## Delivery state

| Claim | Evidence |
|---|---|
| SOURCE | Bounded source_validation endpoint implemented; task's 27 behavior tests passed. Concurrent page-owner additions now introduce two incompatible expectations, recorded below, so current shared gates are not all green. |
| INSTALLED | Wheel1.0.0 built and installed non-editably in linux/amd64 image; UID10001 import/router/projection verified without source mounts/PYTHONPATH/network. Earlier candidate also passed actual ASGI nonempty response through shared auth and AuditStore with provider I/O stubbed. |
| DEPLOYED | NOT PERFORMED: target lacks required monitoring infrastructure/configuration. No push or service mutation. |
| LIVE-FUNCTION-VERIFIED | NOT PERFORMED: no safe existing audit table/auth policy/fixture found. |

Task remains incomplete. This evidence is not a replacement for deployed/live delivery.

## Implemented source and scope

- `be-intake/app/processing_monitor_step_routes.py`: real GET `/v1/cases/{case_id}/processing/documents/{document_id}/runs/{run_id}/steps`; mandatory positive attempt, limit1–100, bounded cursor. Reuses `authorized_document`, `read_authorized_window` and the sole AuditStore. No competing auth or store.
- Exactly one evaluated document Query; filtering after the window, empty items with continuation valid. Wrapped reader continuation binds version/operation/case/document/run/attempt. Inner token validated before Query. No scan-until-filled, no pairing across windows, no RunQueued/AttemptStarted existence inference.
- Explicit source_validation StepStarted/StepFinished/StepFailed field allowlist, actual event identities/sequence/time, optional persisted duration and internal allowlisted error codes. No page_number, content, raw errors, synthetic duration/status/totals.
- Main registration and Dockerfile COPY only. No producer hooks, audit_queries changes or business schema modifications.
- Sole YAML steps DTO now has dedicated exact source_validation branches, required sequence, optional duration, internal safe code enum and explicit SERVICE Bearer reference. General event schemas and other operations retained. Global Bearer scheme was already present at task start, so no duplicate scheme/global change was made.
- Existing store is technically ordered by `EVENT#event_id`, not proposal-wide occurred_at chronology. Steps description discloses evaluated order and no snapshot/latest guarantee. No global reader rebuild or page-local chronological fiction.

## Genuine TDD and local verification

Canonical generated proof: `plans/checkpoints/task-252c7fcd-6de4-4406-813b-e7771d61da74.red-green-proof.md`.

Dependency preflight imported pytest/fastapi/httpx/multipart/boto3/moto/yaml/jsonschema/openapi_spec_validator from project venv. Collection succeeded with27 tests before RED. No dependency/collection failure was treated as RED.

Helper: `/Users/michal/.config/opencode/skills/tdd/scripts/proof-capture.py`, task-specific TASK_ID, root cwd. Exact child argv in both phases:

```sh
env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_step_routes.py
```

- RED run `7e3495e20c0240cfb8247500c6ffa2a0`: helper exit0/accepted_red, child exit1; authorized happy request404 versus expected200. Canonical RED read before production edits.
- Rejected GREEN `b98b91ee7f084cf281560bac48e45057`:26 passed/1 failed. Cross-case fixture accidentally appended duplicate grants and strict policy correctly503. Fixed duplicate fixture without weakening assertions. Diagnostic output retained, not relabelled green.
- GREEN `b3012b86de774a569507d2404f54dd95`: helper exit0/accepted_green, child exit0,27 passed. Canonical proof read after broader verification; neither phase manually edited/reconstructed.

Commands and outcomes:

| Command | Actual outcome |
|---|---|
| `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests` (first run) |353 passed,1 failed: historical pages key-only happy fixture403 vs200. |
| `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` |17 passed; bundled5 functions. |
| `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_openapi_observation_contract.py` |6 passed after dedicated source-validation contract assertion added. |
| Same full Python command after concurrent pages route/tests appeared |384 passed,2 failed in sibling page tests: `test_two_pages_distinct_observations_and_exact_contract`503 vs200 and `test_fail_closed_and_safe_errors[unconfigured]`200 vs503. |
| `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_step_routes.py be-document-processing/tests/test_monitor_openapi_observation_contract.py` (latest focused+contract) |33 passed,2 failed: concurrent page-owner expectations that steps must expose pages, contrary to this authoritative source_validation-only plan. |
| `git diff --check` |exit0, including after scope restoration. |

No skips/ignores/xfails or softened assertions introduced. Registered command has no lint script invoked separately by the plan; whitespace and sole OpenAPI validation ran as above.

### Concurrent ownership conflict (unresolved)

During verification another writer added `processing_monitor_page_routes` imports and `items.extend(page_observations(...))` to this task-owned steps module, and page branches to StepObservation. It also appended `test_page_projection_matches_pages_once_per_terminal` and `test_pages_and_steps_share_exact_page_observation_branches`. This task's explicit approved scope excludes activating page observations. After inspecting the exact edits, only the cross-slice imports/delegation and StepObservation page references were removed; standalone pages route, its registration, DTOs and tests were preserved. A negative page-event assertion was added to this task's source-validation matrix. The conflicting newly appended tests remain intact, failing honestly. Do not infer current all-green from the earlier27-test proof. Owner reconciliation is required; do not expand steps or weaken tests silently.

## Local source → wheel → image provenance

All builds used repository root and existing `be-intake/app/Dockerfile`, no new service/framework:

```sh
docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:steps-task-252c7fcd .
docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:steps-task-252c7fcd-final .
docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:steps-task-252c7fcd-source-validation .
```

All exit0. Wheel SHA256 `ff25e2bebdec73a1e105dfb326fae4be40c769c245712e11c845afb732407510`, installed package1.0.0. Final two builds reused that unchanged wheel layer.

| Local tag | OCI index | linux/amd64 manifest |
|---|---|---|
|steps-task-252c7fcd|`a4c199da2d356c385943a5fea1e190b26faae41912a7854a70d982b9cf01afd1`|`f545a95d0b4a6ddb7d7dac9df584839e688691d023d4dda44a09b5f020ad7518`|
|steps-task-252c7fcd-final (historical concurrent page-expanded steps)|`cae3180a58a438463cb6d7c2eb9f385568ebbf2fa21686968318880c97f2ee04`|`f83633d3f7d134473a64da8fc83d1e69833e9b9e7fc700f6ff39f338f680b278`|
|steps-task-252c7fcd-source-validation (intended candidate)|`0271f14757141e4b9cc3e48cad435dd4d1d67339f34db70a9287a8eb878239a5`|`b0cd98bd6d40cc68e2b31265e124afc45fd50f81be8f7a98692eccfc38e9a049`|

Digests above have `sha256:` prefix. Intended final config digest `sha256:6b40c701863325243c7ae594f6fc469f37fe0d200412d31beb2db72ebc6e3413`.

`docker run --rm --platform linux/amd64 --user 10001 --network none --entrypoint python <tag> -c <inline installed assertions>` executed without mounts, PYTHONPATH or dependency installs. First two candidates executed actual ASGI nonempty steps200/private-no-store through middleware, shared policy/membership and AuditStore with only boto I/O faked; terminal-only event `installed-terminal`, sequence7, attempt1, run-test, duration12.5, source_validation and coverage partial; exactly1 Query/0 Scan. Latest intended candidate explicitly checked installed imports, router, projection, absence of page-module coupling and these installed hashes:

| Installed source | SHA256 |
|---|---|
|`/app/main.py`|`030cfa1be4b2fd8ee7548a3b6d13baac038a5049689497804e0f778d7c52e48a`|
|`/app/processing_monitor_step_routes.py`|`c17f03114301b57e0d33b5fb6abb7818147930172c77e1a7d50a8229ccc8f3be`|
|`/usr/local/lib/python3.12/site-packages/document_processing/audit/audit_events.py`|`45aa5610ae684e3dd54ac43b81608b3d86d18953d5b77e84dbb4572c2f61b673`|

Steps hash matches first ASGI-verified candidate; final main includes concurrent independent pages registration. Shared checkout remains mutable: continuing operator must recheck hashes, never use mutable local tag as deployed provenance.

## Fresh AWS target preflight and concrete blocker

AWS work used official MCP `call_boto3`, not AWS CLI. GetCallerIdentity succeeded for expected TeamAdmin session in account609394381050, eu-central-1. Authentication is available; no IAM denial is invented.

- Existing TEST target: `arn:aws:apprunner:eu-central-1:609394381050:service/wonderfulkb-ingest/c9ef96fae3da4192abd7e8280d43ae6b`; URL `https://vt9mavpjky.eu-central-1.awsapprunner.com`; RUNNING; tag project=wonderfulkb; operational owner Jackie per standing authority.
- Source image `609394381050.dkr.ecr.eu-central-1.amazonaws.com/wonderfulkb-ingest:v7`; auto-deployfalse. Latest listed operation `0dab321464ec41d58fd92e4a4ced64cc`, UPDATE_SERVICE, SUCCEEDED, ended2026-10-19T20:05:24Z. No listed active rollout.
- Runtime env contains only CASES_TABLE, DOCS_TABLE, RAW_BUCKET; secret reference API_KEY. **No AUDIT_TABLE_NAME, PROCESSING_MONITOR_AUTHORIZATION_SECRET_ARN or MONITOR_AUTH_SECRET_ARN.**
- ECR existing repository verified, mutable tags. v7 recovery digest `sha256:f9218fba402683163d6a4ba012a2ea9eb5493b2a2a8aec74b8a512602c0008ae` ACTIVE. BatchGetImage by digest returned manifest (length856) and zero failures. This proves registry availability, not a locally retained/pulled recovery/config backup.
- ListTables returned exactly wonderfulkb-uw-cases, wonderfulkb-uw-clients, wonderfulkb-uw-content-hashes, wonderfulkb-uw-document-analysis, wonderfulkb-uw-documents: **no existing audit table** in this verified region/account.
- ListSecrets returned only ingest-api-key and wonderful-webhook metadata: **no existing monitoring authorization secret**. No secret values read or exposed.
- Instance role `wonderfulkb-ingest-instance` has one inline `data` policy and no attached policies; inspected policy only permits existing raw storage/documents/cases/content-hashes and ingest API-key secret. **No audit-table permissions or monitoring-policy secret permission.**

The approved existing-infrastructure/image rollout cannot make functional authenticated steps reads without these missing dependencies. Plan budget permits at most one guarded update of an EXISTING policy version, not inventing a missing auth source or widening grants. No safe existing monitoring fixture or server-attested membership can be attested in a nonexistent audit source. No business documents were scanned or replayed to manufacture a fixture. No cloud write was made.

### Same-task operator handoff to Jackie

1. Resolve/provide the missing existing TEST audit-table and monitoring auth-policy dependency (actual ARNs, owning deployment, grants and fixture provenance); if provisioning is necessary, reconcile it explicitly against this plan's existing-target/budget constraint. Current task cannot truthfully claim these exist. No request to publish publicly or use production.
2. Reconcile inherited owner/Case Client budgets and obtain the existing deployment serialization guard before mutation. Do not reset budgets. No guard acquired/ownership lease is claimed here.
3. Preserve current service config and recovery image by digest outside repo, including exact environment, secret references, ECR access role, instance role, networking and health configuration. Current service has512 CPU/1024 memory, HTTP /healthz, port8080. Do not replace any unrelated settings.
4. After dependencies exist, bind exact audit table + auth ARN and only minimum scoped existing-owner IAM. Grant only explicitly enumerated reader-only synthetic case/document; no wildcard. Authenticate in a secure channel, never put credential in evidence.
5. Revalidate source hashes and installed source_validation-only route; resolve concurrent page-versus-steps scope conflict first. Push verified immutable task tag to the existing ingest ECR, record registry manifest digest. Local digest is NOT a pushed ECR attestation.
6. Immediately before guarded image/config update re-read DescribeService/ListOperations, current image registry digest and auth-policy VersionId. Abort on drift/active foreign rollout. Update existing service preserving unrelated settings; poll at most15min/15s. Require operation SUCCEEDED + RUNNING + image/config readback before live assertions. Recovery only under still-owned guard.
7. Same-task bounded live fixture: deterministic case/document/run/task IDs with trusted current or retained membership; at most3 labelled reader-only source-validation audit insert attempts through existing idempotent store, if needed. Never call them worker producer proof. Record IDs and provenance before writes. Up to12 GETs prove nonempty precise DTO, continuation, wrong-attempt filtering, cross-scope/operation400, missing-auth403 and no-store. No provider inference/upload/business POST/fault injection. Append real rollout/live responses here after operator execution; presently none exist.

## Request/write ledger

| Operation | Used this session | Limit |
|---|---:|---:|
|Successful signed AWS control-plane reads|13|reported; no polling loop started|
|Prevalidation rejection|1 ListTagsForResource used ServiceArn instead of ResourceArn; corrected once, no AWS request for rejected call|not a cloud mutation|
|ECR push / image rollout / recovery|0 /0 /0|candidate rollouts2, recovery1 after inherited reconciliation|
|Live HTTP GET|0|12|
|POST/upload/business writes / provider inference|0 /0|0|
|Audit insert attempts|0|3, reader-only label required|
|Auth-policy writes / recovery|0 /0|existing guarded update1/recovery1; no policy creation budget assumed|
|New resources / IAM changes|0 /0|no unplanned provisioning|

No ambiguous writes exist to replay. No real document data, Case Client fixture or exhausted budget was modified. Historical failed/inconclusive evidence and authoritative plan unchanged.

## Review/acceptance

Loaded validate-implementation/code-review/write-review-report. Harness denied reference-file reads for configured validation/security workflows; no alternate path bypassed. Scoped manual review checked plan/source, sole YAML, bounded Query, fail-closed policy, document scope, cursor operation/attempt scoping, safe optional fields, image packaging and no business/producer edits. Full skill-configured validation is not claimed complete. No caller acceptance manifest was supplied, so structured manifest acceptance was not fabricated. Mandatory delivery gates remain unmet; no task lifecycle/mark_complete operation was performed.

## Final concurrent-write observation — supersedes current-checkout claims above

Final read found another writer had REINTRODUCED page imports/delegation into `processing_monitor_step_routes.py` after the source_validation-only installed candidate was built. Latest direct focused+contract command above then returned **35 passed**, with changed concurrent tests/DTO agreeing on page expansion. This is a new passing snapshot, not proof of adherence to this task's source_validation-only plan. Earlier failures remain preserved and are not relabelled green. The current checkout does not match the intended installed candidate, and the endpoint's active page expansion is outside this task's explicit scope. No further overwrite cycle was attempted. Resolve writer/contract ownership before any deployment; a fresh source manifest/build and required verification must follow that resolution. Canonical27-test RED/GREEN is unchanged and remains historical evidence for the implemented source-validation behavior. Final review remains NEEDS_FIX for **source scope drift plus absent AWS prerequisites**, even though the latest focused tests pass. Standalone pages source is preserved.
