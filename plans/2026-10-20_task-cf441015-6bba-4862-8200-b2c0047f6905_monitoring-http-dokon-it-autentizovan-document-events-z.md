# Plan 2026-10-20: authenticated document-events delivery

## Progress
- [x] Resolve canonical plan path for task-cf441015-6bba-4862-8200-b2c0047f6905.
- [x] Inspect parent plan/evidence, authorization contract, implementation and learnings.
- [x] Specify focused TDD, shared authorization, artifact and live verification steps.
- [ ] Implement and verify under task-cf441015-6bba-4862-8200-b2c0047f6905 using this canonical plan; planning itself makes no SOURCE/INSTALLED/DEPLOYED/LIVE_VERIFIED claim.

## Analysis
- Reconcile the parent plan with the owner authorization granted on 2026-10-20; preserve completed work and historical acceptance findings.
- Reuse `AuditStore.read_document`/`audit_queries.py` (one Query, limits 1–100, document-scoped cursor) and the post-commit FileReceived producer already in `main.py`; do not rebuild either.
- Replace the unregistered route sketch's missing `intake` fixture with an explicit import from `test_monitor_file_received`; existing `guard()` already supplies monitoring no-store, so its historical no-store assertion is no longer a genuine RED.
- Add both monitoring modules to the existing wheel-installing Dockerfile, which currently copies only main/content_hashes/lifecycle routes. Preserve all pre-existing tracked and untracked work.
- Apply `read-api` in the authoritative proposal over historical authorization blockers; retain missing-identity/no-entitlement distinctions and required `coverage=partial` from the sole OpenAPI contract.
- Use recalled rules for fixture/import readiness, immutable historical proofs, conditional writes, error-preserving reads and inherited cloud budgets. Recall backend: local; collection: wonderfulkb-learnings; diagnostic: collection missing. Apply the 10:01 authorization approval over the superseded owner-seam blocker in `learnings/security-issues/2026-10-20_document-events-authorization-prerequisite.md`.
- Inspect `be-document-processing/PROCESSING-MONITOR-API.md`, the sole OpenAPI YAML and `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md#read-api` together; no PlantUML files were found. Resolve the proposal's chronological timeline versus existing EVENT#identity cursor explicitly before acceptance; do not claim global chronological pagination by sorting individual pages.

## Approach
- Implement `processing_monitor_authorization.py` with a narrow injectable source returning a versioned server-owned authorization document: credential SHA-256 digest→SERVICE principal ID/enabled flag, principal ID→explicit case ID grants, and exact retained case/document membership records with verified commit provenance. Reject wildcard/empty/malformed entries, unknown principal types and duplicate credential bindings; never trust principal/case claims in request headers.
- Store this document in a dedicated secret in the already-used AWS Secrets Manager service, referenced by ARN in App Runner config; grant only GetSecretValue on that ARN to the existing intake instance role. Preserve the existing upload API-key secret and policies. Bearer credentials are random >=256-bit server-only values; store only digests in the authorization document, compare in constant time and deliver raw credentials through the existing secure operator channel. Never log credentials, digests or secret contents.
- Read the authorization secret on every monitoring request with bounded SDK timeout/attempts and no last-known-good fallback. Rotation adds a second digest for the same principal, securely switches the caller, then removes the old digest; revoke by removing digest/grant. Fresh reads observe revocation without process restart. Missing/invalid config or secret read failure returns safe 503 before audit Query; absent/forged/disabled identity or absent/revoked case grant returns consistent 403.
- Authenticate and authorize before membership/audit access. Verify active membership by strongly consistent exact-key documents GetItem and check returned IDs; do not require a surviving case business row. If the document row is absent, accept only an exact server-owned retained membership record derived from previously verified committed metadata, with source revision/verification time. Missing evidence gives 404; membership read failure gives 503 rather than fallback. A guessed document_key or cursor never establishes membership. Retained records do not replace the current case grant.
- Use `processing_monitor_routes.py` as the common monitoring facade: shared authorization/membership dependencies, one installed AuditStore reader, safe event DTO mapping and uniform errors/no-store. Make these seams importable by existing lifecycle and future route modules without implementing their unfinished operations or adding another reader.

## Implementation
1. Preserve parent finding-001/002/003 and checkpoint history; inspect current diff and proof lineage before editing. Use skill:task-evidence for exact historical commands/outcomes. Read-only verify current App Runner/ECR ownership, supported deployment procedure, caller credential channel and existing fixture/request/deploy ledger; historical host references are not current target proof.
2. Implementace TDD cyklu dle skill:tdd: first fix test import/setup and add the executable skeleton below, capture actual behavior RED, then implement adapter/facade. Add remaining negative, pagination and retained-history tests before their implementations. Do not manufacture RED by deleting working code or using missing modules/fixtures.
3. Add the authorization source plus validation/binding/grant/membership adapter. Wire separate monitoring Bearer dispatch in `guard()` only for the exact processing path subtree; shared upload `x-api-key` remains required for upload/list and is neither sufficient monitoring entitlement nor replaced by a monitoring token. Include upload-auth regression assertions proving no new access.
4. Register document-events GET; validate IDs, integer limit 1–100 and token length/scope, then call `AuditStore.read_document` exactly once per page. Return allowlisted event metadata, next_token, UTC observed_at and coverage=partial; safe 400 for invalid inputs/cursor, 403 for denial, 404 for unknown document, 503 for required source/decoder/store failures. Map only request-validation failures to 400, not arbitrary stored-data ValueError. Preserve disabled/unavailable versus truly empty semantics; no configured-store failure becomes empty200.
5. Keep private, no-store on every monitoring response, including middleware auth, validation, unavailable store, exception and unknown route responses. Resolve timeline ordering with the canonical contract owner: retain one bounded identity-ordered Query and explicitly document technical continuation/page display semantics in the existing proposal/guide/YAML if that MVP clarification is approved; otherwise report the exact unresolved contract blocker rather than silently redefining the timeline or introducing a full-history reader.
6. Complete focused GREEN and the regression matrix; add both modules to Docker COPY with readable permissions. Build root-context linux/amd64 image, inspect installed wheel version/source hash and import/registered route as UID10001 with synthetic config. Verify the actual image's authorization and reader wiring, not just host PYTHONPATH.
7. Before mutation, snapshot current target revision/image digest/config references and retain a verified recovery image/config; acquire an execution lock and recheck revision/config immediately before update. Provision the scoped authorization secret/config through the existing owner procedure and narrowly scoped template diff; use skills for AWS containers, IAM, Python SDK and CloudFormation when implementing those portions. Preserve unrelated environment/IAM/auth and do not bypass denials; Jackie handles genuinely inaccessible operator steps within this task.
8. Deploy the installed image by immutable digest in-place to the verified eu-central-1 AWS TEST App Runner; boundedly wait for completed operation/health, then read back actual image digest, operation/revision/time and redacted config identity. Abort mutation on revision drift; use the verified recovery artifact for a guarded rollback on rollout/regression failure. Record failed attempts unchanged.
9. Execute the bounded synthetic live sequence in Testing; account for each request/write and distinguish fixture provisioning, producer event, installed image and deployed HTTP result. Close findings only with task-local evidence; run skill:validate-implementation after code completion and skill:save-learning as the final delivery phase, saving at least one applicable learning.

## TDD
- Focused file: `be-intake/tests/test_processing_monitor_routes.py`; command for both RED and GREEN: `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_routes.py`.
- Verify venv FastAPI/httpx/pytest/python-multipart and audit imports before capture. Use supported skill:tdd proof at `plans/checkpoints/task-cf441015-6bba-4862-8200-b2c0047f6905.red-green-proof.md`. Parent setup failure is not a valid RED; reuse any applicable genuine ancestor proof with provenance, never overwrite it. Existing working no-store is not the missing feature.
- Replace the broken sketch with this runnable first behavior test; the app-state source/store names below define the injection contract for the planned facade. Fake only provider I/O; credential binding and membership decisions must execute real adapter logic.

```python
import hashlib
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from test_monitor_file_received import intake  # noqa: F401
from document_processing.audit.audit_storage import AuditStore


def test_authorized_service_reads_document_events(intake):
    main, _, docs, _, _, _ = intake
    credential = "synthetic-only-credential-0123456789abcdef"
    source = MagicMock(return_value={
        "version": 1,
        "credentials": [{"sha256": hashlib.sha256(credential.encode()).hexdigest(),
                         "principal_id": "monitor-test"}],
        "principals": [{"id": "monitor-test", "type": "SERVICE", "enabled": True,
                        "case_ids": ["case-test"]}],
        "retained_documents": [],
    })
    main.app.state.processing_monitor_authorization_source = source
    docs.get_item.return_value = {"Item": {"case_id": "case-test", "document_id": "doc-test"}}
    table = MagicMock()
    table.query.return_value = {"Items": [{
        "schema_version": 1, "event_id": "received-test", "sequence": 0,
        "case_id": "case-test", "document_id": "doc-test", "type": "FileReceived",
        "occurred_at": "2026-10-20T10:00:00Z",
    }]}
    main.app.state.processing_monitor_audit_store = AuditStore(table)
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/cases/case-test/processing/documents/doc-test/events",
            headers={"Authorization": f"Bearer {credential}"},
        )
    assert response.status_code == 200  # RED today: upload guard returns 401, route absent
    assert response.json()["items"][0]["event_id"] == "received-test"
    assert response.json()["coverage"] == "partial"
    assert response.headers["cache-control"] == "private, no-store"
    source.assert_called_once()
    table.query.assert_called_once()
    table.scan.assert_not_called()
```

| Behavior | Genuine RED before change | GREEN requirement |
|---|---|---|
| Authorized SERVICE+grant above | 401 instead of authorized200 | Bound identity, real membership check, one Query, FileReceived DTO |
| Forged/missing identity; key-only; wrong/revoked grant | Missing adapter/incorrect status or read count | 403 and zero audit Query |
| Secret malformed/unavailable; membership failure | Missing error mapping | 503, zero audit Query, no stale fallback |
| Two pages; cross-case/document/malformed cursor; invalid limit | Route missing/incorrect pagination | Exact continuation, one Query/page; invalid cursor400 before Query |
| Missing business row with trusted retained membership | Route missing | Same case grant required, authorized history200; guessed/foreign scope404 |
| Audit read/decode/disabled failure | Route missing | Safe503, no empty success, no-store |
- Extend the same focused file with these cases, credential rotation/old-token rejection and retained grant revocation. Assert exact documents GetItem keys/ConsistentRead and no business existence prerequisite for retained history; confirm all applicable statuses carry no-store. Use real AuditStore cursor generation over stubbed Query pages, not fabricated success DTOs.

## Testing
- Run `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests be-validator-agent/trigger/tests be-validator-agent/pipeline/tests`; retain all relevant Python assertions and collect failures without ignores. Run registered gate verbatim: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- Prove hermetic upload→post-commit FileReceived→real AuditStore→HTTP with the exact returned case/document, plus producer duplicate/fail-open parity already covered in `test_monitor_file_received.py`; do not relabel mocked producer integration as live evidence.
- Set a task-local ceiling before first cloud mutation: at most two forward image rollouts plus one guarded rollback, one auth-secret creation with at most two version updates, one explicit synthetic case grant and one upload request containing at most two tiny synthetic PDFs; at most 30 monitoring/health HTTP reads and 10 exact-key fixture preflight reads. Count any inherited attempts against the applicable existing budget; stop at exhaustion or ambiguous write outcome. Do not spend or reset the separate Case Client POST/deploy budget.
- Reuse a verified existing synthetic case; do not create a case via Case Client in this task. Confirm the document stream's actual route for this fixture cannot invoke paid inference/provider before upload; use only an already-supported no-provider path. If none exists, record that concrete live blocker without disabling shared processing or uploading anyway.
- Upload tiny generated synthetic PDFs once through real intake auth, record committed case/document IDs and response timing, then authenticate the separate SERVICE credential and GET events for those exact IDs. Assert FileReceived identity/time from the commit, safe DTO, partial coverage and private/no-store. No direct audit insertion may stand in for this producer proof.
- Verify live missing/forged identity, shared-key-only, ungranted case and unknown document safely; use an actual returned cursor for continuation/cross-document400 if the verified fixture already has >=2 events. Keep two-page correctness mandatory hermetically; if the live fixture lacks a cursor, report live pagination unverified rather than invent events or enable inference. Test audit-read503 hermetically, without shared-cloud fault injection.
- Retained membership live preparation may add only the exact verified committed tuple/provenance to the secret; never delete live business rows to test retention. Prove row-loss/retained authorization hermetically. Keep secret version identifiers and sanitized config hashes, never contents/digests/credentials, in evidence.
- Write `plans/monitoring/task-cf441015-6bba-4862-8200-b2c0047f6905-http-evidence.md` and task checkpoint with source tree hash (including untracked owned source), wheel/image digest, recovery verification, concurrency guard/config diff, deployed revision/time, safe response assertions and request/write ledger. Mark SOURCE / INSTALLED / DEPLOYED / LIVE_VERIFIED separately and link findings/proof/gate outputs; permanent403 or a blocker note cannot close functional acceptance.

## Files
| Path | Planned change |
|---|---|
| `be-intake/app/processing_monitor_authorization.py` | Shared strict secret-source, credential/principal/case binding and retained-membership adapter |
| `be-intake/app/processing_monitor_routes.py` | Shared facade, document-events GET, safe DTO/error handling, one bounded reader |
| `be-intake/app/main.py` | Scoped auth dispatch, dependencies/router registration, all-response no-store; preserve upload guard |
| `be-intake/app/Dockerfile` | Copy both modules into existing non-root wheel-installed image |
| `be-intake/template.yaml`, `be-intake/README.md` | Dedicated authorization secret/ARN-only read permission and secure configuration/rotation procedure |
| `be-intake/tests/test_processing_monitor_routes.py` | Supported focused TDD matrix and shared fixture import |
| `be-intake/tests/test_monitor_file_received.py` | Reuse producer/HTTP fixture; extend integration only where necessary |
| `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml`, authoritative proposal | Align only approved auth/error/ordering clarification; no extra endpoints or second contract |
| Task-local checkpoint/proof/evidence paths above; `learnings/security-issues/` | Preserve lineage, capture actual execution and save scoped learning |
- Use discovered skills `tdd`, `task-evidence`, `validate-implementation`, `save-learning` at the steps above; use `write-review-report` if performing a distinct review phase. Invoke `wful` only if Wonderful platform operations become necessary; this delivery targets the existing AWS intake deployment.
