# Signature read delivery — task-095a56a6-1e34-4c79-9649-07a109f27928

## Delivery status

| State | Actual result |
|---|---|
| SOURCE | Implemented and verified. Signature observations use the existing steps mapper and document/run event DTO. |
| INSTALLED | Verified non-editable audit wheel1.0.0 in final native linux/amd64 intake image, UID10001/network-none, no source mounts or PYTHONPATH. |
| DEPLOYED | **NOT DEPLOYED.** Current runtime is the older run-events artifact; its exact retained image does not allow signature observations in steps. |
| LIVE-FUNCTION-VERIFIED | **BLOCKED.** No transferred deployment guard/shared budget; exact approved synthetic membership absent and bounded audit partition empty. No genuine signature run/attempt/event observed. |

Overall **INCOMPLETE**, not source-only DONE. No mark_complete, commit, publication, plan edit or acceptance override. Remaining operator action is within this delivery, not deferred to a new task.

## Narrow implementation and ownership

- `be-intake/app/processing_monitor_step_routes.py`: three explicit signature_detection StepStarted/StepFinished/StepFailed allowlist entries, same FACT_FIELDS/optional terminal duration/safe failure code; existing mapper, page delegation, reader and cursor unchanged.
- `be-intake/app/processing_monitor_routes.py`: only this task's public StepFailed allowlist addition `SIGNATURE_DETECTION_FAILED`, retaining safe code parity with steps. Existing shared authorization/document membership/no-store/read503 reused.
- Sole `be-document-processing/contracts/openapi-processing-monitor.yaml`: three closed Signature*Observation branches, public StepFailed enum and existing steps semantics updated. Other operations and sibling attempts work preserved.
- Focused FastAPI tests and installed image smoke verify terminal-only facts, optional duration, completed-empty/failed/start-only/absent, exact privacy projection, steps/document/run parity and pages exclusion. Stored failed events represent returned/raised failure equally; tests do not call or claim to call a detector.
- No reader/store/producer/execution/business/config/IAM/storage/index changes. No whole-history pairing, Scan, fill loop, inferred historical config/status/skipped/model-call/results/counts.
- Initial worktree already had shared facade/YAML/image smoke modifications and attempts tests. They were investigated and preserved. The final image includes that sibling attempts source; this is disclosed, not attributed to this signature task.

## Genuine test-first proof

Canonical helper-generated proof: `plans/checkpoints/task-095a56a6-1e34-4c79-9649-07a109f27928.red-green-proof.md`.
Helper discovered through `skill:tdd`: `/Users/michal/.config/opencode/skills/tdd/scripts/proof-capture.py`.

Same exact child argv in both phases:

```sh
env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_signature_observations.py
```

- RED `6d1d54ebe2f944c2b5840c3e47847dcf`, timestamp2026-10-20T11:09:33.846878Z: helper0/accepted_red, child1, **10 failed/17 passed**. Authorized200 returned empty steps rather than persisted signature events. No collection/import/auth fixture error. Read canonical accepted RED before production edits.
- GREEN `137d618618fd4c12bbc235db445cc40e`, timestamp2026-10-20T11:10:09.253476Z: helper0/accepted_green, child0, **27 passed**. Same command. Proof never manually edited or reconstructed; both sections read back after broad gates.
- Tests assert one bounded evaluated Query/request, exact Limit/ExclusiveStartKey, empty continuation, run/attempt isolation, case/document/run/operation/attempt token binding, malformed token400/no extra Query, no Scan.
- Real shared authorization seam: missing/shared-key/forged/revoked/disabled/ungranted403; missing/foreign document404; required auth/membership/audit/decode/nonfinite/unsafe-code503; required positive attempt400; private,no-store on all. Read503 is hermetic only.
- OAS30Validator validates actual signature StepCollection responses and rejects extra properties including signature contents/counts/config/page_number/model_call/status.

## Commands and results

All below exited0:

```sh
env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests
npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build
docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:signature-task-095a56a6 .
docker run --rm -i --platform linux/amd64 --user 10001 --network none --entrypoint python wonderfulkb-ingest:signature-task-095a56a6 - < be-intake/tests/image_processing_monitor_smoke.py
docker build --platform linux/amd64 --target package-builder -f be-intake/app/Dockerfile -t wonderfulkb-ingest:signature-wheel-095a56a6 .
docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:signature-task-095a56a6-final .
docker run --rm -i --platform linux/amd64 --user 10001 --network none --entrypoint python wonderfulkb-ingest:signature-task-095a56a6-final - < be-intake/tests/image_processing_monitor_smoke.py
git diff --check
```

- Full Python **504 passed**,19 dependency warnings, both before and after concurrent facade change; includes signature event/store and sole OpenAPI gates. Backoffice **29 passed**, build bundled9 functions; module-type warnings preserved. No separate lint command specified; diff whitespace check passed.
- Concurrent owner hardened shared run cursor encoding after initial build (facade d7cf60bb... →3c14ffce...). Preserved it, built a separate final tag and reran signature/routes/attempts regression **139 passed**, then full Python504 passed. Historical first artifact not relabelled.
- Both installed image smokes passed: actual installed FastAPI/auth/membership/AuditStore/router, provider I/O stubbed; nonempty signature StepFinished and StepFailed/duration2.5/code parity with document/run events, pages exclusion, one Query/private,no-store and all prior assertions retained. **Hermetic artifact evidence, not live worker proof.**

## Source → wheel → image provenance

| Artifact | SHA256 |
|---|---|
| FINAL local OCI index | `a5d1a95aa1f9fc3cbf971d18cb86e071adf448933c57c0693e49e7b8db5f0e52` |
| FINAL linux/amd64 manifest | `7f1f453318c5f47e70c28fb54e1f626b759ea7570ddd38d82bdb21280f5f5d17` |
| FINAL config | `bc9051e5084438d1d95cf19325d92a32306dca712cbacc1736e45614dfbdecbf` |
| Final native source-input aggregate | `428cc3ad8fe85f38446eb42790bf0ea0d6614e2328de04577dbb97fe4d877940` |
| Installed audit wheel1.0.0 | `2e291b0787b0a90646896b8b12e7895f911a6a9d3a3a293ba45961521f071bf6` |
| Final steps source | `f5add78e0e31c76b6d64aedfb8ba79d0fe41bb04fb8914df186191da6f14a962` |
| Final shared facade | `3c14ffce6389bfc1556d9cda8692fbfd4f140135f19ce3a98721ca5ac35cc41c` |
| Audit reader | `db56ce0be958a19185f4c044d179db3ecf78a7281589061cc5fa46589ae49304` |
| Focused signature tests | `110f8f9e6a6a65fc64f147a2a21011e08df24ddeea5d600ae2e091476d9c22ae` |

Aggregate command, run before and after final build with equal output:
`git ls-files -z --cached --others --exclude-standard be-intake/app be-document-processing/src be-document-processing/pyproject.toml be-document-processing/requirements.txt | xargs -0 shasum -a 256 | shasum -a 256`.
Installed smoke printed14 Python source hashes (7 intake/7 audit), all equal to host shasum verification. Final candidate retained as `wonderfulkb-ingest:signature-task-095a56a6-final`; not pushed. Package-builder `/wheels/*.whl` hash verified; installed distribution direct_url archive SHA256 matches it, `editable` false, file URL under `/wheels/`, audit imports in site-packages. No editable/source mount shortcut.

Initial retained artifact (before sibling facade hardening): index`a0521a5f22e90a99ece6179c4b6dc3e0304712041e95caf7918404dc10d8885e`, amd64`631ae7f90eea6c06ccd72ff2ad55c08f1fe48104aa80d46cb354ca3add375ab2`, config`d746d6bc380ad992418ffe4f0cfdfe6f8e7e7c0ca80fe78d68409d018a50e299`; initial tag remains unchanged. Use FINAL candidate for continuation, after fresh source comparison.

## Fresh AWS preflight, recovery and exact fixture

Official AWS MCP only for AWS APIs; successful `api_calls` checked. Signed STS verified account609394381050 and expected `AWSReservedSSO_ai-hackathon-TeamAdmin_9fe3bd578b2d8334` session. Region eu-central-1; no default-profile or authentication blocker, no write-permission claim from reads.

- At11:11:03Z exact approved ingest service RUNNING, HTTPS host discovered as `vt9mavpjky.eu-central-1.awsapprunner.com`; current image `609394381050.dkr.ecr.eu-central-1.amazonaws.com/wonderfulkb-ingest:task-1d77ce99-e462d804`. Auto-deployfalse, CPU512/memory1024/existing role, HTTP /healthz configuration retained.
- Latest operation `e5bcdf6b57c74901a5befeb9678f8add` UPDATE_SERVICE SUCCEEDED, start09:59:05Z/end10:10:25Z. It is historical sibling deployment, **not this task's new signature image**.
- ECR verified current recovery index`sha256:e462d804b114d426df9d61e1b686f29afc07859ddd5ab3133dadb259585f9b8a`, amd64`sha256:99f39a86c78d8dbf6582d4accf082aa0f92af069fae29795d56a2c78154ad856`, config`sha256:260e97aa9897c948214044d2b2c3b40ada3063d62ab6dcc5b404c88e8ea7c7ef`,0 failures. Pulled exact digest locally, retained without pruning, verified UID10001/site-packages1.0.0 and step router import. Its steps hash02623a55... and `signature_allowed=false` explicitly prove it is NOT the candidate.
- Safe recovery SourceConfiguration/instance/network/health/autoscaling reference snapshot at11:12:21Z: `plans/monitoring/task-095a56a6-1e34-4c79-9649-07a109f27928-recovery.json`. Only resource names and secret ARNs, no values. Refresh/compare and retain protected full configuration under owner before any mutation.
- `.intake-deployment.lock` still PID86998; ps shows no process. Neither lock removal nor ownership takeover was performed. Prior owner evidence specifies shlock but supplies no explicit transfer/reconciled shared remainder to this task. A dead PID is not a budget or ownership grant.
- At11:11:34Z exact ConsistentRead GetItem on `wonderfulkb-uw-documents`, key `(SYN-A01,34fcd896-107a-583f-a406-6a8100cf8150)`, IDs-only projection: **no Item**. Policy AWSCURRENT now`35622c70-c3e9-4817-9933-ff07d3fad4de`, schema_version1, contains active exact current grant. Policy is not membership. No bearer/API key read or token-hash binding claimed.
- One bounded ConsistentRead Query Limit20 on canonical compact JSON document partition `["SYN-A01","34fcd896-107a-583f-a406-6a8100cf8150"]`: Items[]/Count0/ScannedCount0, no continuation. Projection only event identity/type/run/attempt/stage/time; no Scan/history fill or contents. No actual signature run/attempt/event ID available.
- Fresh worker revision`eee08757-ded9-4db5-8935-60bfab7db4ef`, modified11:07:23Z, Active/Successful, now has EXECUTION_TABLE and AUDIT_TABLE_NAME. Resolved image`sha256:ba79db597636eb250142cb4f50a2c39f345a5d07d2036860639b19a68dae248d`. **Old missing-env blocker no longer current.** Compatible deployed writer/reader source chronology is not established by env names/image identity. Local reader still uses EVENT#event_id order; do not claim chronological read or migrate schema in this patch. Coordinate existing native readiness owner.

## Ledger and actual HTTP assertions

| This task operation | Consumption |
|---|---:|
| Signed STS / DescribeService / ListOperations |1 /2 /1|
| Worker GetFunctionConfiguration / GetFunction |1 /1|
| ECR BatchGetImage |2|
| Policy GetSecretValue / exact membership GetItem / bounded audit Query |1 /1 /1|
| Registry recovery pull / import verification |1 /1|
| ECR push / forward rollout / rollback |0 /0 /0|
| Live HTTP GET / POST / upload / audit or metadata writes / provider calls |0 /0 /0 /0 /0|
| IAM/auth/grant/schema/resource mutations |0|

No live HTTP status, ID or schema success is claimed. No request was reserved/sent against an unknown inherited shared remainder; no invented run/attempt or empty200 substituted. Current absent membership and empty partition are direct AWS preflight facts, not live route proof. Shared deploy/HTTP budgets and Case Client budget unchanged; local12 GET/2 candidate+1 recovery ceilings are not renewed allowances.

## Same-delivery Jackie operator continuation (blocking)

1. Explicitly transfer/reconcile existing intake guard and shared deploy/HTTP ledger, including sibling rollout and GET consumption. Preserve lock/history; no new allowance inferred from this task. Resolve current exact synthetic membership discrepancy through its actual metadata owner and provide a genuinely observed permitted signature event/run/attempt with provenance, or identify a specifically supported authorized path. No manual metadata/audit INSERT, replay, inference, queue or downstream case work to manufacture proof.
2. Review the included sibling attempts facade state with its owner, freshly compare aggregate428cc3ad... and installed hashes; abort/rebuild on drift. Retain full protected recovery/config and exact ECR index above. Expected service config diff: **only SourceConfiguration.ImageRepository.ImageIdentifier**; all existing env/secrets/IAM/auth/network/health/autoscaling/auto-deploy preserved.
3. Under that guard, native remaining packaging/push commands are:
   `docker tag wonderfulkb-ingest:signature-task-095a56a6-final 609394381050.dkr.ecr.eu-central-1.amazonaws.com/wonderfulkb-ingest:signature-task-095a56a6-a5d1a95a`
   then `docker push 609394381050.dkr.ecr.eu-central-1.amazonaws.com/wonderfulkb-ingest:signature-task-095a56a6-a5d1a95a`.
   Verify registry index/platform/config against FINAL digests. Pull success does not prove push IAM permission.
4. Fresh DescribeService/ListOperations/config/recovery/source comparison immediately before native `call_boto3(service_name="apprunner", operation_name="UpdateService", region_name="eu-central-1", params={"ServiceArn": <exact recovery ARN>, "SourceConfiguration": <fresh copied SourceConfiguration with only verified candidate ImageIdentifier changed>})`. No standalone unguarded update authorized by this note. App Runner has no CAS RevisionId: owner lock plus fresh operation/image/config comparison; abort on drift. Reserve from actual remaining min(shared remainder,2 forward+1 recovery), bounded15min/15s polling. Require SUCCEEDED/RUNNING and actual registry/platform/config/time readback. Rollback only against this task's unchanged owned revision; never overwrite foreign revision.
5. Once fixture and ledger permit, in-memory retrieve exact signing-in-to-aws credentials with explicit ai-hackathon/eu-central-1 or same verified MCP identity; validate token hash/state/exact grant/current membership. Reserve GETs before execution, at most min(shared remainder,12), no redirects/retries. Bounded document-events discovery must establish real run/attempt/event, then direct steps signature DTO/no-store/partial/scoping, document/run parity/pages exclusion and relevant continuation/auth negatives. Read503 remains hermetic. Record actual sanitized assertions/IDs/counts. If observations remain absent, LIVE-FUNCTION-VERIFIED stays unmet;200empty is insufficient.

No supported host-message/operator execution tool is exposed in this coding session; this explicit in-repo handoff and final blocker notice request the required narrow host step, not a new task or source-only acceptance.

## Scoped validation/review

Manual review target: the three allowlist entries, one public code, own YAML branches/steps operation, focused tests, installed smoke and package/source provenance. Exact fields/unknown semantics/terminal-only parity, existing authorization before single bounded Query, operation/attempt-bound tokens, read503/no-store and no business writes remain intact. No additional production defect identified in this patch.

Loaded validate-implementation and code-review. Exact Read calls denied for `/Users/michal/.config/opencode/skills/validate-implementation/workflows/plan-compliance.md`, `/Users/michal/.config/opencode/skills/code-review/workflows/security.md` and `/Users/michal/.agents/skills/aws-containers/references/ecr.md`. Preserved denials; no alternate-tool bypass. Full configured review cannot be claimed. Signing-in-to-aws exact reference was readable and followed. No caller acceptance run manifest supplied, no fabricated acceptance result. Canonical review report uses NEEDS_FIX for incomplete runtime delivery; caller forbids new/modified plans, so no fix plan created.

Recall helper ran once: backend local, collection wonderfulkb-learnings, diagnostic Collection not found. Read all10 returned files and signature-specific learning; applied task-wide budget preservation, source/install/deploy/live distinction, producer identity, bounded Query/read-failure rules. Global case Scan/UUID advice is unrelated and not applied; older event-only no-deploy scope does not override this read task's explicit authorization.

Final save-learning skill and discovered add-frontmatter.py helper succeeded with --output `learnings/tooling/2026-10-20_signature-read-public-code-image-provenance-and-runtime-blockers.md`. Temporary content used workspace tmp/task-095a56a6-signature-delivery-learning.md. Task remains operationally blocked, no completion claim.
