# Execution table — reviewed candidate, deployment pending

Task: `task-17168021-af35-40d3-a30f-165cc6bfbae9`

## What was implemented

Prepared a native SAM UPDATE candidate from the actual deployed Original template, retained protected recovery configuration and verified existing artifacts, and created/reviewed a CloudFormation change set. No application source was changed. **The change set has not been executed; the requested infrastructure is not yet deployed.**

## Exact operator target

- Account/region: `609394381050 / eu-central-1`, independently confirmed by signed MCP and explicit `ai-hackathon` SDK STS.
- Stack: `arn:aws:cloudformation:eu-central-1:609394381050:stack/wonderfulkb-trigger/a0e34ef0-cbfa-11f1-b0fa-06db8b417f09`.
- Change set: `arn:aws:cloudformation:eu-central-1:609394381050:changeSet/execution-table-task17168021-20261020/d6787119-558d-4f18-aed2-025532247dd4`.
- Observed change-set state: `CREATE_COMPLETE / AVAILABLE`, created `2026-10-20T10:18:35.984Z`.
- Create client token: `task17168021-execution-table-review-20261020`; request ID `afbdd347-aed3-4e60-bab0-1673fd7a8157`.
- `candidate.json` SHA-256: `e380470638711a61deba8c8b05577b86f87e331e79001c92b42f4f87a28517aa`, 35,742 bytes.
- Original template SHA-256: `76f7025b7ee10dd91c27c96b5ae29b34ebaa41e7c9cd0b5b3e43a74b1d39938b`.
- Source HEAD: `d70cb89419c51af1c6c29548f0cd75206427c149`; existing trigger-template dirty-diff SHA-256: `dbed15cfb4cdb79750b3e5b61d463187c3f0b07bf9457d7f3570524962aef1d4`.

## Review findings

Native property-level review and exact Processed-template comparisons passed for this allowlist:

| Resource | Action | Allowed delta |
|---|---|---|
| ExecutionTable | Add | canonical pk/sk String, on-demand billing, PITR, both Retain policies |
| EnqueueFunction | Modify, Replacement=False | add EXECUTION_TABLE and AUDIT_TABLE_NAME |
| WorkerFunction | Modify, Replacement=False | add EXECUTION_TABLE and AUDIT_TABLE_NAME |
| EnqueueRole | Modify, Replacement=False | append three resource-scoped inline statements |
| WorkerRole | Modify, Replacement=False | append three resource-scoped inline statements |

All Modify details require recreation `Never`. All existing statements, trust policies, artifact references, mappings, queue/stream definitions, concurrency, remaining environments and other properties/top-level template entries are unchanged in the processed candidate.

DLQ source calls analysis/queue operations, not execution allocation/claim or audit append; no DLQ permission/env expansion is justified. Both actual producer callers use shared common execution code; bindings are prepared for their separate artifact rollout, not evidence that those artifacts already contain new producers.

Transaction IAM uses GetItem/PutItem/UpdateItem on execution and ConditionCheckItem on execution/analysis, retaining existing analysis Get/Put/Update. Audit receives only PutItem on the existing audit table. The canonical source's `dynamodb:TransactWriteItems` entries were not copied as a substitute for item authorization. AWS reference: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis-iam.html . No business transaction code was changed.

## Recovery

Task-relative `recovery/` is ignored, directory mode 0700, generated snapshot files 0600. It contains actual Original/Processed templates, stack config/parameters/tags/policy, all three Lambda GetFunction/configuration/revisions/code/environment/concurrency, mappings, queue attributes, documents stream/table config, audit table config, IAM roles/policies, native change set and processed candidate. Do not copy these private objects into reports.

- `recovery/snapshot.json`: SHA-256 `22a0c6ed36f3c4b9df0d1265b010ec9b3c453b562fd4c87126a640919a4920fa`.
- `recovery/iam.json`: SHA-256 `01270fc22b4aab3c432c924b783b5b568acdc4f8ef0b05adbac9b56f200115d4`.
- `recovery/light.zip`: 7,107 bytes, verified base64 SHA-256 `K73HXLSxEXnxTgGV47ibuLsow7TFlA3slHUug002KM8=` matches both deployed ZIP functions. Original versioned S3 object remains available.
- Original worker ECR artifact is ACTIVE and its original tag still resolves to `sha256:8d5eefda655e050c28f81f5be831d8f453d70c1cbcf71d634a37c1dd3f8c00e6`.

## Verification already run

All commands below exited 0:

1. Root: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` — 21 tests passed, 0 skipped; 7 functions bundled. Existing Node package-type warnings remain.
2. Trigger cwd: `PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=..:../../be-document-processing/src .venv/bin/python -m pytest tests/test_template.py tests/test_execution_owner.py tests/test_enqueue.py tests/test_worker.py tests/test_dlq.py tests/test_audit_instrumentation.py -q -ra` — 63 passed, no skips; existing venv cfn-lint was used.
3. Trigger cwd: `PATH="$PWD/.venv/bin:$PATH" AWS_PROFILE=ai-hackathon AWS_REGION=eu-central-1 AWS_DEFAULT_REGION=eu-central-1 sam validate --lint --template-file template.yaml`.
4. Root: `be-validator-agent/trigger/.venv/bin/cfn-lint plans/checkpoints/task-17168021-af35-40d3-a30f-165cc6bfbae9/candidate.json`.
5. Root: `PATH="$PWD/be-validator-agent/trigger/.venv/bin:$PATH" AWS_PROFILE=ai-hackathon AWS_REGION=eu-central-1 AWS_DEFAULT_REGION=eu-central-1 sam validate --lint --template-file plans/checkpoints/task-17168021-af35-40d3-a30f-165cc6bfbae9/candidate.json`.
6. AWS `ValidateTemplate` under verified target identity, then CreateChangeSet with all 13 existing parameters `UsePreviousValue`, unchanged tags/capabilities and unchanged absent service-role setting.
7. `git diff --check`.

The canonical proof was generated by the loaded TDD helper before candidate creation, then read back. RED was accepted (`0e0d0d79debc4655a304b051537d351f`, child exit 1) for a real missing table assertion, not an environment/collection failure. **GREEN is pending actual deployment**; a local valid candidate cannot make a live acceptance assertion pass. Do not edit the proof manually or close acceptance from local gates.

## Remaining Jackie/operator step — same delivery

1. Confirm an exclusive bounded deployment window with the current host owner, as required by authoritative plan implementation step 8. This session asked for that confirmation and has not received it. Standing TEST authorization exists; this is coordination for CloudFormation's missing Lambda RevisionId CAS, not a request for broader deployment authority.
2. Immediately before executing, reverify signed account, exact stack stable status/LastUpdatedTime/Original template/parameters/tags/role, every Lambda revision/config/code/digest, IAM policies/boundaries/attachments, ECR tag/digest, mappings, queue and documents stream against the protected recovery state. Initial stack LastUpdatedTime: `2026-10-20T08:18:31.773Z`. Any conflict requires reinspection and a new reviewed change set, never overwrite.
3. Recheck this exact change-set ARN is still AVAILABLE and exactly the reviewed candidate. Execute only this ARN, with a unique recorded execute client token. Do not replay an ambiguous request; inspect first. No out-of-band Lambda updates.
4. Poll bounded every 15 seconds up to 15 minutes. Preserve actual failures/events; no destructive rollback/delete/import/replacement or repeated deployment for idempotency proof.
5. After UPDATE_COMPLETE, fresh DescribeTable/PITR and CFN ownership/retention readbacks; env and role-specific IAM readback; compare all unrelated configuration/artifacts to recovery. Report effective authorization YES/PARTIAL/NO according to actual boundary/SCP/resource-policy evidence; current boundary absence alone does not prove effective access.
6. Run the exact focused command through the same helper:

   `TASK_ID=task-17168021-af35-40d3-a30f-165cc6bfbae9 python3 /Users/michal/.config/opencode/skills/tdd/scripts/proof-capture.py green -- be-validator-agent/trigger/.venv/bin/python plans/checkpoints/task-17168021-af35-40d3-a30f-165cc6bfbae9/test_live_execution_resource.py`

   Require `accepted_green`, child exit 0 and read back the exact canonical proof. Keep task incomplete until actual execution/readbacks and proof satisfy acceptance.

## Goals met/unmet

- [MET] Signed target inspection, real missing-resource RED, protected recovery and verified original artifacts.
- [MET] Validated native candidate and exact no-replacement change-set allowlist review.
- [MET] Registered local gates.
- [UNMET] Execution table ACTIVE and owned by deployed stack; change set not executed pending exclusive-window coordination.
- [UNMET] Deployed env/IAM readback, effective permissions and post-deployment artifact/config preservation proof.
- [UNMET] Genuine GREEN section in canonical proof.

## Findings by severity

### P1 — Critical
None in the reviewed candidate.

### P2 — Important
Deployment coordination and execution/readbacks remain pending; this is not a completed infrastructure delivery. New producer image rollout remains a separate owner task. No producer-to-audit-to-HTTP success is claimed.

### P3 — Minor
External SDK reference reads were denied by filesystem scope; no alternate tool/path was used to bypass those denials. AWS MCP disallowed importing yaml; local supported SDK was used for protected local artifact capture and exact local candidate submission. No AWS CLI was used. Review artifacts stay within the explicitly authorized repository scope; no external orchestration report or new fix plan was written.

## Goals unmet
- Deployed table/wiring and post-deployment readbacks.
- Matching live GREEN proof.

## Verdict: NEEDS_FIX

Remaining work is the concrete operator continuation above, not a new evidence-only task. No business data, audit rows, uploads, queue messages, HTTP smoke, paid inference or downstream case steps were generated.
