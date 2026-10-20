# Extraction steps delivery evidence — task-12f46945-d733-47dc-b0e9-b8c9746fd7c2

## Continuation — 2026-10-20T10:16:44Z (current status)

The sections below this continuation are historical and retained verbatim. No source-only completion is claimed.

| State | Current result |
|---|---|
| SOURCE | Extraction implementation retained; narrowly hardened steps cursor JSON against duplicate scope keys, with genuine test-first HTTP RED/GREEN. |
| INSTALLED | Final corrected candidate built and installed smoke passed as UID10001/network-none, without source mounts or PYTHONPATH. |
| DEPLOYED | Original extraction implementation is now confirmed in the sibling deployed runtime by exact manifest/config match. **Final duplicate-key correction is NOT deployed.** No deployment mutation by this continuation. |
| LIVE-FUNCTION-VERIFIED | **NOT VERIFIED.** Current exact authorized synthetic document metadata read is absent; audit partition is empty. No genuine run/attempt/extraction fixture or transferred shared GET ledger. |

### Actual source correction and proof lineage

- Re-read exact authoritative plan first; own checkpoint did not exist, so created only the required task checkpoint. No plan/brief changed. Initial characterization: focused15 passed, full Python444 passed; backoffice21 passed/build7 functions.
- Scoped review found that a steps cursor containing both `attempt_no:2` and `attempt_no:1` was accepted with HTTP200 and an extra Query. This violates unambiguous malformed/scope cursor rejection. Only `processing_monitor_step_routes._unwrap` changed: local `json.loads(object_pairs_hook=...)` rejects duplicate object keys, following the already existing run-events parser pattern. Shared auth/reader, Query, schemas and other operations unchanged by this continuation.
- Focused test constructs an actual returned continuation and adds conflicting duplicate attempt scope. Expected400/private,no-store and no second Query. Canonical helper RED run `3e65f54a847b4b3db4c3d0a31f0feca0`, 2026-10-20T10:15:18.947761Z: helper0/accepted_red, child1, actual HTTP200 !=400. Read accepted RED before production edit.
- Matching helper GREEN run `95da77d7d01c42f98da6756e8383ba56`, 2026-10-20T10:15:35.908985Z: helper0/accepted_green, child0, **17 passed**. Exact argv unchanged from historical proof: `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_extraction.py`.
- Helper archived original extraction4-failure/4-pass cycle under this task's `.cycles/` directory; it was not reconstructed or deleted. Current canonical proof was read back after broader verification and contains genuine duplicate-scope RED and GREEN sections.
- **Explicitly excluded proof attempt:** first nested-token test expected the wrong error envelope (`detail`, but this app returns `error`). Helper mechanically accepted RED run `b9a1ddd17f804027998127aec3d005d5`; this was a test expectation error, NOT a production defect or valid implementation RED. Corrected test only, GREEN `2dc7d9199b4542ffa2b4a7a8f6e99c13`; this intermediate cycle is retained in helper archives, not claimed as implementation proof. Increasing nesting within token size bounds also passed; helper rejected false RED `19cc3338a54f479dae219a7dfccb2699`. No production edit was based on either attempt. The nested-token case remains a characterization regression. The subsequent duplicate-key RED above is genuine and is the current canonical cycle.

### Final verification (all exit0)

```sh
env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests
npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build
docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:extraction-task-12f46945 .
docker run --rm -i --platform linux/amd64 --user 10001 --network none --entrypoint python wonderfulkb-ingest:extraction-task-12f46945 - < be-intake/tests/image_processing_monitor_smoke.py
git diff --check
```

- Python **446 passed**,17 dependency warnings; focused helper GREEN17 passed. Sole YAML schema/contract gates included; no separate lint command in plan. Backoffice **21 passed**, bundled7 functions. Warnings not hidden.
- Installed smoke preserves extraction failure duration/error document/run parity, pages exclusion, nonempty page/source/cache observations, bounded continuation, cross-run400, grant403/read503/private-no-store. It now also includes concurrent cache-owner smoke assertions; those source edits were preserved. Provider I/O mocked, **not live producer proof**.
- Final image intake/audit hashes match all14 host modules after build. Source manifest computed by the same method documented below; only step route hash differs from pre-fix runtime.

| Final corrected local candidate | SHA256 |
|---|---|
| OCI index | `d28f7dce36b3e263482de3790e4d90d92b9b19ccc85e9808f93238001b023aca` |
| linux/amd64 runtime manifest | `3141d0b46a770648edcd31f8f25ecd862ccc8b243ef34ba438665162bba9030e` |
| Config | `2bf99914ee00e9428e248bd29aa69a41bd82f0af98c3efc17ff0373f221739e4` |
| Installed audit wheel1.0.0 (unchanged cached package-builder stage, freshly hashed) | `00ff410534211c144fbb57d7c456eb4ec4f3fdfd7b8f4b1bb671369615215bc5` |
| Scoped14-module source manifest | `6b7d35a4c69a9380697d7e765a89638dc564ee52153a4a357fee424bddb802e2` |
| Final step route | `49411e6d3b56805b6fa45ff1144abcdbdb771fa6be9f20a5318322134a27d8f8` |

Local tag retained: `wonderfulkb-ingest:extraction-task-12f46945`. Final candidate has NOT been pushed. Wheel-builder target retained as `wonderfulkb-ingest:extraction-wheel-12f46945`. No worker dependencies installed into intake.

### Fresh AWS readback and honest deployed distinction

Official AWS MCP, eu-central-1; signed STS at10:11:29.437807Z verified account609394381050 and expected ai-hackathon-TeamAdmin role. Each successful call's `api_calls` checked. Reads do not prove deploy/write permission.

- DescribeService/ListOperations at **10:12:08.261588Z**: exact approved App Runner target remains RUNNING at `https://vt9mavpjky.eu-central-1.awsapprunner.com`, image `609394381050.dkr.ecr.eu-central-1.amazonaws.com/wonderfulkb-ingest:task-1d77ce99-e462d804`. Auto-deployfalse; CPU512/memory1024/existing instance role; health HTTP `/healthz`, interval10/timeout5/healthy1/unhealthy5. Existing audit/auth env names present.
- Sibling operation **`e5bcdf6b57c74901a5befeb9678f8add` UPDATE_SERVICE SUCCEEDED**, start2026-10-20T09:59:05Z/end10:10:25Z. This continuation did not submit/poll/replay that update; fresh completed readback establishes its outcome. Existing owner rollout/recovery narrative is in `task-1d77ce99-3b09-48f7-9978-e0e99783c9b5-run-events-evidence.md`.
- Two ECR BatchGetImage reads at **10:12:24.639622Z**, no failures: deployed tag index `sha256:e462d804b114d426df9d61e1b686f29afc07859ddd5ab3133dadb259585f9b8a` references linux/amd64 manifest `sha256:99f39a86c78d8dbf6582d4accf082aa0f92af069fae29795d56a2c78154ad856`, whose config is `sha256:260e97aa9897c948214044d2b2c3b40ada3063d62ab6dcc5b404c88e8ea7c7ef`. These EXACTLY match the initial pre-correction build and installed extraction smoke in this continuation. Initial local index `sha256:dabd5d49cfcfffc3fb270dd345580bcd80a16132ca6be542a4ce9a0c81936692` differs only in attestation entry. Thus original extraction source/runtime deployment is established by bytes, **not by a similar tag**. New corrected manifest3141d0b4... is distinct and not deployed.
- Existing `.intake-deployment.lock` contains PID86998; `ps -p 86998 -o pid=,etime=,comm=` returned no process. Lock not removed or acquired. Stale PID alone is not transferred owner serialization or a reconciled shared budget.
- Policy-only GetSecretValue at **10:13:05.486280Z**: AWSCURRENT `dee3153b-291e-48ac-83bd-ba89aa59a695`, schema_version1, exact SYN-A01/document34fcd896-107a-583f-a406-6a8100cf8150 grant is active/current. No bearer/API-key retrieval or hash-binding assertion; no HTTP attempted. Only safe policy facts returned.
- **Fresh exact ConsistentRead GetItem** on `wonderfulkb-uw-documents`, key `(SYN-A01,34fcd896-107a-583f-a406-6a8100cf8150)`, projection case_id/document_id, returned `{}` (no Item). This differs from09:57:31 historical membership evidence; absence is current, reason unknown, no cause inferred and no restoration write attempted.
- One bounded ConsistentRead audit Query Limit20 on the exact JSON document partition, projection event identity/type/run/attempt/stage/time, returned Items[]/Count0/ScannedCount0 and no continuation. No Scan, producer/run/attempt inferred, business values, replay or seed.

### Remaining same-task operator action and ledger

1. Jackie must reconcile/transfer the existing intake serialization guard and inherited request/deployment ledger; do not reset allowance from sibling operation or a new image. Existing lock is not owned by this task. Confirm current membership and supply an already-authorized, genuinely observed nonempty extraction event/run/attempt plus provenance. No metadata insert/audit seed/upload/replay/model call is authorized by this task to create proof.
2. Retain complete protected current App Runner configuration and verified recovery image before any mutation. Candidate source hash/manifest/config above; target ARN unchanged below. **Config diff: image identifier only.** Current deployed index e462d804... is registry-verified; previous host recovery d6764bd1... and owner's protected recovery remain historical references, not a claim this continuation retained full recovery configuration.
3. Under transferred guard, inspect/recompare final candidate source and fresh service/operations/auth version; abort on drift. Tag/push the retained final candidate into EXISTING ingest ECR, verify registry/platform digests, then native App Runner UpdateService changing only `SourceConfiguration.ImageRepository.ImageIdentifier` in a copy of fresh SourceConfiguration. App Runner has no CAS RevisionId; use owner lock plus fresh comparison. Do not run an unguarded standalone update from this evidence. Enforce min(shared remainder,2 candidate rollouts+1 recovery),15min/15s bounded wait, SUCCEEDED/RUNNING/digest/config readback. Owner handles exact unsupported operator step in this task; no new task/framework/access expansion.
4. After genuine fixture and policy/hash-binding/current-membership validation, reserve before request and perform direct authenticated steps HTTP using actual run/attempt, then parity/pages/scope/continuation assertions within min(shared remainder,12 total GET). Current proof has no live status/schema assertions, no invented IDs and no200empty substitution. Auth/read503 remains hermetic. If no trusted fixture exists, leave LIVE-FUNCTION-VERIFIED unmet.

| This continuation operation | Consumption |
|---|---:|
| ECR push / candidate rollout / recovery |0 /0 /0|
| Live HTTP GET / POST / business or audit writes / provider calls |0 /0 /0 /0|
| Signed STS / DescribeService / ListOperations / ECR BatchGetImage |1 /1 /1 /2|
| Policy GetSecretValue / exact membership GetItem / bounded audit Query |1 /1 /1|
| MCP code prevalidation rejections (no child/API ran) |2 (blocked __import__, blocked hashlib import; removed hashing, no bypass)|

Historical per-task minimum totals including earlier section: metadata reads3, audit Query2; HTTP/push/rollout/recovery/business writes remain0 for this task. Sibling rollout1 is acknowledged above but NOT silently charged as an independently reset allowance or performed by this continuation. Shared remainder unknown.

### Validation/review limits and recalled rules

- Manual scoped review: extraction steps mapper/DTO, shared DTO parity seam, reader, focused tests, sole YAML and installed image; no additional source defect found after duplicate-key fix. Closed fields, terminal-only/unknown semantics, one Query/no Scan, fail-closed auth and no-store/read503 maintained. No new endpoint/index/projection/producer.
- Loaded validate-implementation and code-review. Read denied again for `/Users/michal/.config/opencode/skills/validate-implementation/workflows/plan-compliance.md` and `/Users/michal/.config/opencode/skills/code-review/workflows/security.md`; aws-containers `/Users/michal/.agents/skills/aws-containers/references/ecr.md` likewise denied. No alternate-tool/path bypass; full configured review cannot be claimed. Signing-in-to-aws exact reference read succeeded. No caller acceptance manifest supplied.
- Recall helper ran once: backend local, collection wonderfulkb-learnings, diagnostic Collection not found. Read all10 returned files. Applicable rules: retain real historical proof, never reset inherited budget, distinguish source/image/live, propagate read failures, preserve producer-supplied identity. Global case Scan/UUID rules are unrelated and were not applied; older event-only no-deploy scope does not override this task's explicit authorization.
- Review report appended at canonical host path. Overall **NEEDS_FIX / INCOMPLETE** for final deployment/live and auxiliary review access; no mark_complete or lifecycle override.

---

## Historical evidence (before this continuation)

## Delivery state

| State | Result |
|---|---|
| SOURCE | Implemented and locally verified. |
| INSTALLED | Verified non-editable wheel 1.0.0 in existing linux/amd64 intake image; UID10001, no mounts/PYTHONPATH/provider network. |
| DEPLOYED | **NOT PERFORMED for this artifact.** Existing host-frozen rollout is a different artifact. Owner serialization guard/shared remaining budget not established. |
| LIVE-FUNCTION-VERIFIED | **NOT VERIFIED.** Current authorized synthetic document has no stored audit observations; no extraction event provenance or safe nonempty fixture available. |

Task remains INCOMPLETE. No mark_complete, publication, commit or task lifecycle override performed. Historical evidence and the authoritative plan are unchanged.

## Implementation and scoped review

- Existing `processing_monitor_step_routes.py` explicit allowlist now includes extraction StepStarted/StepFinished/StepFailed. Existing bounded reader, auth/document-scope seams, page mapper, cursor and registration reused.
- Only actual event identity/type/sequence/time/run/attempt/stage and known optional terminal duration/safe failure code are returned. No document payload/page_number/status/model-call claims or synthesized pairing/outcome/duration.
- Actual run-events route now exists; plan-time missing interface is resolved by sibling work. Focused parity tests use the same stored events through steps/document events/run events and prove each matching ID once; pages excludes extraction.
- Necessary narrow shared DTO correction: StepFailed now retains persisted duration and `EXTRACTION_FAILED` instead of coarsening it to PROCESSING_FAILED. Sole YAML admits those fields, makes generic StepFinished duration optional (terminal-only observation may omit it), and adds three closed extraction observation branches plus partial/unknown semantics to the existing steps operation.
- Existing source/page/cache behavior preserved; updated the old extraction-exclusion assertion. No reader/store/index/producer/business execution changes.
- Review target: step route, narrow shared DTO edits, sole YAML, extraction tests, adjusted step assertions and image smoke. Manual scoped checks cover allowlist privacy, fail-closed auth, one Query/no Scan, operation/run/attempt cursor scope, empty continuation and image packaging.
- Loaded validate-implementation and code-review. Harness denied their plan-compliance/security reference reads; did not bypass the restriction. Full skill-configured review is not claimed. Manual plan compliance finds runtime delivery unmet, not an implementation pass for the entire task. No caller acceptance manifest supplied.

## Genuine TDD and verification

Helper: `/Users/michal/.config/opencode/skills/tdd/scripts/proof-capture.py`.
Canonical helper-generated proof: `plans/checkpoints/task-12f46945-d733-47dc-b0e9-b8c9746fd7c2.red-green-proof.md`.

Exact child command for both phases:

```sh
env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_extraction.py
```

- RED run `9a7737620c2a43d7bb1f61a6494a9451`: helper exit0, accepted_red, child1; four real assertion failures. Authorized HTTP200/partial returned no extraction items. RED proof read before production edits; no import/auth/collection failure used as RED.
- GREEN run `59f121c02ffb42ff90b1ea02ae02257b`: helper exit0, accepted_green, child0;4 passed for same command. No manual proof transcription. Both sections read back after broader gates.
- Subsequently added regression-only continuation/auth/scope/read-error cases: same focused command **15 passed**. Original proof is preserved, not reconstructed to imply those later cases were in the original cycle.
- `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests`: initially433 passed; after additional tests **444 passed**,17 warnings.
- `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`: **21 passed**, build bundled7 functions; existing module-type warnings only.
- `git diff --check`: exit0. No separate lint script is required by this plan; no lint success invented.
- OAS30Validator validates actual extraction StepCollection responses and rejects added page_number/fields/status/model_call properties. Existing sole-contract validator gate also passes in full Python suite.
- Focused cases: start→finish/failure, start-only unknown, terminal-only without duration/start, separate stage/run/attempt, empty evaluated window with continuation, exact ExclusiveStartKey/Limit, wrong run/attempt/operation/malformed cursor400 without further Query, missing/shared-key/revoked403, document404, auth/read/decode503, private,no-store on all responses and no raw values.

## Source → installed wheel → image

Executed existing supported root-context build, exit0:

```sh
docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:extraction-task-12f46945 .
docker run --rm -i --platform linux/amd64 --user 10001 --network none --entrypoint python wonderfulkb-ingest:extraction-task-12f46945 - < be-intake/tests/image_processing_monitor_smoke.py
```

Smoke passed using real installed authorization/membership/AuditStore/ASGI; only boto provider I/O stubbed. Nonempty extraction-image-terminal StepFailed/EXTRACTION_FAILED/duration2.5 matches document/run events; pages empty; existing FileReceived/cache/page/cursor/auth/error assertions preserved. This is artifact proof, not deployed/worker proof.

| Artifact | SHA256 |
|---|---|
| Local OCI index | `dc410b03e50508123958dea69415a74b6d8d0fc6f512e7f05949ee65d3bf383c` |
| linux/amd64 manifest | `99f39a86c78d8dbf6582d4accf082aa0f92af069fae29795d56a2c78154ad856` |
| Config | `260e97aa9897c948214044d2b2c3b40ada3063d62ab6dcc5b404c88e8ea7c7ef` |
| `wonderfulkb_document_processing-1.0.0-py3-none-any.whl` | `00ff410534211c144fbb57d7c456eb4ec4f3fdfd7b8f4b1bb671369615215bc5` |
| Scoped Python source manifest | `c8188fd1b7c8cde819338c5fc7f0b5be291ddefa0ae1c4a6b943ce5b5992e468` |

All digests have `sha256:` prefix. Wheel hash read from cached SAME package-builder stage via `docker build --platform linux/amd64 --target package-builder -f be-intake/app/Dockerfile -t wonderfulkb-ingest:extraction-wheel-12f46945 .` and network-none Python hashing of `/wheels/*.whl`. Runtime image installs it with --no-deps; package version1.0.0 read via importlib.metadata. No new dependency/package framework introduced.

Source manifest is the JSON mapping of sorted `be-intake/app/*.py` and `be-document-processing/src/document_processing/audit/*.py` paths to SHA256, hashed with json.dumps(sort_keys=True,separators=(',',':')). This is a scoped14-module manifest, not a claim that every repository file is frozen. Host hashes after build exactly match installed image smoke hashes for all14 modules. In particular:

| Source | SHA256 |
|---|---|
| step routes | `02623a55fb2b55c9dee2d337dd5a0350048b2a28dd1fb525bc13ef511e72bf28` |
| shared routes | `c9adeaa02bcf382ebb087b0153f09bbf76c372910c475eb7c1684ebf0b9a2c64` |
| main | `030cfa1be4b2fd8ee7548a3b6d13baac038a5049689497804e0f778d7c52e48a` |
| authorization | `5527838db9e75a0aa1c721a7d2c46c62f81a115778c8b867c0e215291df5b96a` |
| audit_events | `45aa5610ae684e3dd54ac43b81608b3d86d18953d5b77e84dbb4572c2f61b673` |
| audit_queries | `db56ce0be958a19185f4c044d179db3ecf78a7281589061cc5fa46589ae49304` |

Local image is retained under task tag; it has NOT been pushed or attested in ECR. Shared checkout may change; continuing operator must recompare source and image hashes.

## Fresh AWS preflight — do not reuse obsolete missing-infrastructure verdict

Official AWS MCP only; each returned api_calls entry checked. STS succeeded for expected TeamAdmin in account609394381050/eu-central-1; no missing-credential or write-denial claim.

- Existing target `arn:aws:apprunner:eu-central-1:609394381050:service/wonderfulkb-ingest/c9ef96fae3da4192abd7e8280d43ae6b`; URL `https://vt9mavpjky.eu-central-1.awsapprunner.com`; RUNNING; tag project=wonderfulkb. Operational owner Jackie per standing authority.
- Current image `609394381050.dkr.ecr.eu-central-1.amazonaws.com/wonderfulkb-ingest:host-frozen-20261020-1102`, auto-deployfalse, CPU512/memory1024/existing instance role. UpdatedAt returned2026-10-19T11:49:08Z, so it must NOT be treated as a sufficient revision guard.
- Latest operation `224a177ab8d54226adf8c569aefca482`, UPDATE_SERVICE, SUCCEEDED;2026-10-20T09:03:44Z→09:14:33Z. This is prior HOST rollout, not this task's source deployment.
- Existing ECR recovery index `sha256:d6764bd1bfa64dc5c89c0ffd026984a3c6c89bbb7e5cf4eba9bfad8b96aa375b`, ACTIVE. BatchGetImage by digest returned856-byte manifest and0 failures. Registry recovery availability verified; this task has NOT retained a complete protected recovery/config backup and does not claim a deployment-ready rollback.
- Audit table `wonderfulkb-uw-document-processing-audit` ACTIVE, pk/sk keys. Runtime env now contains AUDIT_TABLE_NAME, CASES_TABLE, DOCS_TABLE, RAW_BUCKET, MONITOR_AUTH_SECRET_ARN and PROCESSING_MONITOR_AUTHORIZATION_SECRET_ARN; API_KEY remains a secret reference. Historical evidence's missing-table/auth findings are no longer current.
- Current auth policy `wonderfulkb/monitoring-synthetic-20261020`, AWSCURRENT version `dee3153b-291e-48ac-83bd-ba89aa59a695`, LastChanged2026-10-20T09:45:43.574Z. Metadata explicitly synthetic-monitor-test. Contains legacy schema_version1 SERVICE document-scoped grants; existing authorization adapter already supports this schema. No policy migration or expansion made.
- Read-only membership preflight2026-10-20T09:57:31.458876Z used2 exact GetItem with projection case_id/document_id: `(9fbe90e5-c36d-4986-8b52-d6b53ccf5a6f, monitor-host-probe-20261020)` absent; `(SYN-A01,34fcd896-107a-583f-a406-6a8100cf8150)` present. Both are current-membership policy grants, not invented retained attestations.
- One bounded Query Limit20/ConsistentRead on the latter exact audit partition, projecting only event_id/type/run_id/attempt_no/stage/time, returned **0 events, no continuation**. No extraction run/attempt/event ID or producer provenance established. No document values fetched.
- Owner's existing report `/Users/michal/.openclaw/workspace/reports/wkb-manual-deploy-20261020/deployment-result.md` corroborates prior host artifact and positive-data proof gap; historical failures remain unchanged. Current exact membership check above supersedes that report's historical absence for SYN-A01 only, not its absence of extraction proof.

## Concrete blockers and same-task Jackie operator continuation

1. Existing deployment serialization guard/acquisition procedure and remaining inherited Case Client/deployment budget are not supplied in repo deployment evidence/runbooks located in this run. No ownership acquired and no budget reset. Jackie must supply/transfer the existing guard and remaining ledger, then recheck source/config/auth version and latest operations immediately before any mutation.
2. No trusted existing extraction event fixture. Current granted metadata is present for SYN-A01, but exact partition is empty. Supply a previously proven synthetic extraction event/run/attempt and its producer provenance/current grant. This task allows0 new writes and forbids manual audit insert/replay/model execution to manufacture positive evidence.
3. Before update retain full current service config and verified recovery image securely outside repo. Proposed config diff is **image identifier only** to an immutable tag/digest of the candidate above. Preserve env/secrets/auth/IAM/network/health/CPU/memory and auto-deployfalse. Recovery availability is verified, protected retention not yet done.
4. Under the transferred guard push candidate to EXISTING ingest ECR, verify registry digest/platform and source manifest, re-read DescribeService/ListOperations/auth VersionId/config fingerprint and abort on foreign operation/drift. No App Runner RevisionId/CAS is assumed. At most min(remaining budget,2 candidate rollouts+1 recovery);15min bounded wait/15s polling. Require operation SUCCEEDED, RUNNING and fresh digest/config readback.
5. Agent/operator then completes direct HTTPS verification IN THIS TASK: at most min(remaining budget,12 GETs), nonempty precise extraction ID/schema/partial/no-store; attempt isolation, document/run parity, pages exclusion, continuation where fixture allows, cross-run/operation400 and missing/ungranted auth per existing policy. No cloud faults; read503 already hermetic. Record sanitized response assertions and request IDs; no credentials/content. Health/empty200/local image smoke cannot satisfy this.

## Session request/write ledger

| Operation | Used | Boundary |
|---|---:|---|
| ECR push / candidate rollout / recovery |0 /0 /0|Guard+remaining shared budget unresolved; local candidate2/recovery1 ceiling not reset.|
| Live HTTP GET |0|12 maximum across candidates, smaller inherited remainder wins.|
| Business/audit writes, uploads, POST/replay/model calls |0|0 authorized for this task's smoke.|
| Auth-policy / IAM / new resources |0 /0 /0|No expansion or provisioning.|
| Exact synthetic membership reads / bounded audit Query |2 /1|Projection-only, no Scan, Query Limit20; no matching events.|
| Read-script prevalidation rejection |1|Blocked `.__name__` access; child/API did not run. Corrected shape-only read once.|

No ambiguous non-idempotent operation exists to replay. No secrets or document content were written to evidence. No safe live HTTP success is claimed. Remaining deployment and positive extraction proof are same-task blockers, not source-only DONE or a deferred new integration task.
