# Attempts delivery evidence — task-dc9a8eab-2900-4aca-9a80-4411cebc0472

## Delivery state

| State | Result |
|---|---|
| SOURCE | Implemented: attempts GET, operation-bound shared cursor, three-field observation DTO, sole YAML and README. |
| INSTALLED | Native root Docker build installs audit wheel1.0.0; final linux/amd64 image passes real ASGI smoke as UID10001 without network. |
| DEPLOYED | **NOT YET** for this candidate. Fresh App Runner still points to sibling run-events image. No update submitted. |
| LIVE-FUNCTION-VERIFIED | **NOT VERIFIED**. Shared guard/budget not transferred; no current authorized genuine AttemptStarted fixture established. No fabricated run or empty200 claim. |

Task remains incomplete on required runtime delivery. Authoritative plan is unchanged. This evidence records actual outcomes, not an acceptance waiver.

## TDD and local gates

Canonical proof: `plans/checkpoints/task-dc9a8eab-2900-4aca-9a80-4411cebc0472.red-green-proof.md`.
The discovered tdd helper captured actual output before production edits:
- RED `be8d4bd7743949b198a2fae17b252b4d`, accepted_red/helper0/child1, timestamp2026-10-20T11:07:33.244888Z. Authorized route returned404 instead of200; collection/import succeeded.25 failed/6 passed.
- GREEN `e11ebc174edf47caaeeea222bac25bde`, accepted_green/helper0/child0, timestamp2026-10-20T11:08:16.784411Z.31 passed.
- Identical argv: `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_attempt_routes.py`.
- RED was read before production edits; GREEN/proof read back after broader verification. Proof was never manually edited.

Focused coverage: two observed attempts plus distinct conflicting identity at same ordinal; second-run/FileReceived exclusion; absent RunQueued; one Query/evaluated limit, empty continuation and exact ExclusiveStartKey; document/run-events/attempts token isolation both directions; scope/type/duplicate/padding/oversize/inner token rejection before Query; current auth/revocation/membership; safe503/read/decode/DTO; private,no-store; sole YAML collection validation, UTC, required/closed DTO and negative bool/zero/extra fields.

Commands actually run:
1. `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests`: **504 passed** (includes concurrent signature tests).
2. `env PYTHONPATH=be-document-processing/src:be-validator-agent/trigger:be-validator-agent/pipeline be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests be-validator-agent/trigger/tests be-validator-agent/pipeline/tests`: initially682 passed/1 skipped; after concurrent signature source was preserved and final candidate rebuilt, **709 passed/1 skipped**,44.22s. No failures, ignores or unrelated repairs.
3. `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`: **29 passed**, bundled9 functions.
4. `git diff --check`: pass.

No standalone lint command is configured for this Python slice; contract validation is part of the above suite. Existing deprecation warnings retained.

## Artifact and source provenance

Native build: `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:task-dc9a8eab .` passed, installed wonderfulkb-document-processing1.0.0 wheel SHA256 `2e291b0787b0a90646896b8b12e7895f911a6a9d3a3a293ba45961521f071bf6`.
Initial image index `sha256:35b6c476fcba10820d5575cd71ea9c92d6ea52f22bed6d1f72784b82420ae65a`, manifest `sha256:08bdd5f628dc558fff9c7a61372ac706b2593464da3476139cfffdb26e2dc25a`, config `sha256:75a709d36d0267a0d010aedc5160020d79aeea5c272b03ebc8eea25030b1786c`. Initial installed smoke passed. This initial image is retained, not represented as current source after sibling changes.

Concurrent signature task changed shared facade/step module/YAML/smoke. Preserved those changes; corrected only own indentation and added own README/smoke label. Rebuilt using:
`docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:task-dc9a8eab-final .`

Final local candidate (not yet pushed):
- Index `sha256:3ae6b9212c84a83a5a6dc7fce5674f4235afcd61f06b9d8c8acbbd5c65541fe5`.
- Runnable amd64 manifest `sha256:7f1f453318c5f47e70c28fb54e1f626b759ea7570ddd38d82bdb21280f5f5d17`.
- Config `sha256:bc9051e5084438d1d95cf19325d92a32306dca712cbacc1736e45614dfbdecbf`.
- Final aggregate source SHA256 `428cc3ad8fe85f38446eb42790bf0ea0d6614e2328de04577dbb97fe4d877940` from `git ls-files -z --cached --others --exclude-standard be-intake/app be-document-processing/src be-document-processing/pyproject.toml be-document-processing/requirements.txt | xargs -0 shasum -a 256 | shasum -a 256`. Includes uncommitted build inputs. Dockerfile is included under app; no commit/provenance fiction.
- Installed facade SHA256 `3c14ffce6389bfc1556d9cda8692fbfd4f140135f19ce3a98721ca5ac35cc41c`; step module `f5add78e0e31c76b6d64aedfb8ba79d0fe41bb04fb8914df186191da6f14a962`; unchanged audit reader `db56ce0be958a19185f4c044d179db3ecf78a7281589061cc5fa46589ae49304`.
- Every installed intake/audit Python hash was emitted by smoke; local shasum comparison establishes same audit files and final shared source. Build uses installed wheel, not PYTHONPATH source.

Final installed verification:
`docker run --rm --platform linux/amd64 --network none --user 10001 -i --entrypoint python wonderfulkb-ingest:task-dc9a8eab-final - < be-intake/tests/image_processing_monitor_smoke.py`
passed. Real ASGI dispatch/auth/membership/AuditStore with stubbed provider clients verifies nonempty exact attempts DTO, second-run exclusion, one Query/request, empty continuation, cross-operation400, private,no-store, and existing document/run/pages/steps including signature compatibility. This is **hermetic installed-artifact proof, not AWS producer/HTTP proof**.

## Fresh AWS target and recovery

AWS MCP signed STS verified609394381050, expected AWSReservedSSO_ai-hackathon-TeamAdmin identity; all calls explicitly eu-central-1, api_calls checked. No default-profile inference, login or IAM change.
Target owner Jackie; existing service:
`arn:aws:apprunner:eu-central-1:609394381050:service/wonderfulkb-ingest/c9ef96fae3da4192abd7e8280d43ae6b`.
Fresh DescribeService at **2026-10-20T11:13:10.877694Z**: RUNNING, described HTTPS host `vt9mavpjky.eu-central-1.awsapprunner.com`, image `609394381050.dkr.ecr.eu-central-1.amazonaws.com/wonderfulkb-ingest:task-1d77ce99-e462d804`.
Latest listed operation `e5bcdf6b57c74901a5befeb9678f8add` SUCCEEDED,09:59:05Z–10:10:25Z. This is a sibling deployment, **not this attempts candidate**.

ECR DescribeImages confirms current/recovery index `sha256:e462d804b114d426df9d61e1b686f29afc07859ddd5ab3133dadb259585f9b8a` ACTIVE. Exact-digest `docker pull --platform linux/amd64` succeeded; image retained locally. No prune.
Complete currently returned source/instance/health/network/autoscaling/encryption/observability config is preserved at `task-dc9a8eab-2900-4aca-9a80-4411cebc0472-recovery.json`; only resource references, no secret values. Intended diff: **ImageIdentifier only**. Preserve CPU512/memory1024, IAM, env, secret references, port8080, health/healthz and auto-deployfalse.

Fresh DescribeTable: audit ACTIVE, pk HASH/sk RANGE, strings, no secondary index. Reader retains technical EVENT#event_id order; no chronology migration/backfill/Scan. Fresh worker GetFunctionConfiguration: revision `eee08757-ded9-4db5-8935-60bfab7db4ef`, modified2026-10-20T11:07:23Z, Active/Successful, **execution and audit env now present**. This supersedes historical env-absent evidence only; neither actual writer content nor producer-image/reader compatibility is established by env presence alone. No worker change made by this task.

## Guard, ledger and concrete blockers

Existing `plans/monitoring/.intake-deployment.lock` contains PID86998; `ps -p 86998 -o pid=,etime=,comm=` returned no process. No lock removal, takeover or ownership claim. Sibling run-events evidence acknowledges forward1/2, HTTP1/20, conservative fixture4/10 consumed; cache evidence separately has HTTP1/12 and metadata reads. Other sibling evidence explicitly leaves shared remaining balance/transfer unknown. These are **not this task's replenished allowances**. No explicit owner-confirmed shared remainder found, so plan Implementation6 forbids guessing/reserving new rollout/HTTP/fixture budgets. Case Client budget untouched.

Current session ledger:
- App Runner mutations/rollouts/rollback0; ECR pushes0; HTTP GET0; fixture GetItem/Query0.
- POST/upload/business/audit writes/queue/inference/policy/IAM changes0.
- Resource-control reads only: STS1; DescribeService2; ListOperations1; DescribeImages1; DescribeTable1; GetFunctionConfiguration1. All api_calls success. Three code-prevalidation rejections (__import__, hashlib import, __name__) ran no AWS APIs; retained as diagnostics, not permission failures.
- No secrets retrieved or HTTP credentials stored. Access reference itself read successfully.

Last known exact synthetic tuple SYN-A01/document34fcd896-107a-583f-a406-6a8100cf8150 returned missing membership and actual document GET404 in run-events evidence. **Not freshly rechecked here**, because shared fixture/HTTP balance is unconfirmed. No known real observed run/event ID is available to this task; do not invent one. Nonempty DTO, continuation and scoping on live attempts remain unmet.

Filesystem read denials retained without alternate-tool bypass:
- `/Users/michal/.agents/skills/aws-containers/references/ecr.md`
- `/Users/michal/.config/opencode/skills/validate-implementation/workflows/plan-compliance.md`
- `/Users/michal/.config/opencode/skills/code-review/workflows/full-review.md`
Native repo deployment procedure and manual scoped review used; full configured skill workflows cannot be claimed complete through these denials.

## Same-delivery operator continuation for Jackie

1. Transfer/resolve existing intake owner lock and supply confirmed remaining shared deploy/HTTP/fixture ledger (retain all prior consumption; no Case Client reset). This is a prerequisite within this task, not a new delivery task. Freshly compare service/operations/full preserved configuration before any mutation; abort on drift or foreign rollout.
2. Candidate above is installed locally. Recheck current source/installed hashes including concurrent work; if unchanged, tag/push using existing native owner Docker/ECR authentication:
   `docker tag wonderfulkb-ingest:task-dc9a8eab-final 609394381050.dkr.ecr.eu-central-1.amazonaws.com/wonderfulkb-ingest:task-dc9a8eab-3ae6b921`
   then `docker push 609394381050.dkr.ecr.eu-central-1.amazonaws.com/wonderfulkb-ingest:task-dc9a8eab-3ae6b921`.
   Verify registry index equals3ae6b921… plus runnable manifest/config above. A successful read/pull is not proven push/deploy permission.
3. Under native `shlock -p "$PPID" -f plans/monitoring/.intake-deployment.lock` owner guard and confirmed reservation, use fresh DescribeService SourceConfiguration unchanged except ImageRepository.ImageIdentifier=`609394381050.dkr.ecr.eu-central-1.amazonaws.com/wonderfulkb-ingest:task-dc9a8eab-3ae6b921`; call native App Runner UpdateService on exact ARN. No App Runner CAS RevisionId exists; compare complete source/config/latest operation immediately before call. Capture OperationId/time, bounded poll15min/15s until SUCCEEDED+RUNNING, then read back image/digests/config. No blind resubmit on ambiguous result. Recovery above only under still-owned guard/current revision.
4. Establish currently existing already-authorized synthetic membership and genuine AttemptStarted observation/run/event IDs with trusted provenance. Fresh worker env changes alone are insufficient. Use access reference's in-memory active hash binding/grant validation and exact membership checks inside confirmed remaining budget. No metadata/audit seed, historical replay/upload, queue send, paid inference or grant widening.
5. Resume bounded real HTTPS verification in **this delivery** using described current host, no redirects and both secret-loaded headers. Read only bounded observations to select real IDs; directly assert attempts nonempty exact event_id/positive attempt_no/occurred_at, partial/UTC/private,no-store, second-run exclusion; continuation/cross-operation400 where fixture permits; current auth/scope policy. Record actual statuses/request IDs/counts without contents/headers. Read503 remains hermetic. Until then do not mark_complete or claim deployed/live success.

## Scoped review

Reviewed own facade/codec/DTO, focused tests, installed smoke, README and own sole-YAML changes; preserved concurrent signature changes. One shared auth/membership/reader/error implementation; no Scan/fill loop/new store/producer/business change. Run-events default cursor bytes preserved, attempts operation validated before audit I/O. DTO closed and safe; conflicting ordinals retain distinct event identities; storage conditional identity remains existing implementation. Sole YAML inherited security matches first GET; effective auth is unchanged. Registered regression/contract/idempotence gates green. No further source defect found. Mandatory deployed/live goals remain blocked; review cannot approve full delivery. No acceptance manifest supplied, no acceptance result fabricated. Required proof file exists and has genuine RED/GREEN.
