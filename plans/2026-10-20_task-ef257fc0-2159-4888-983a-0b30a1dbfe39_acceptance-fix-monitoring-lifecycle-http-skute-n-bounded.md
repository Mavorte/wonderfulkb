# Plan 2026-10-20: Monitoring lifecycle authorization, publication and live proof

## Progress
- [x] Resolve canonical plan path for task-ef257fc0-2159-4888-983a-0b30a1dbfe39.
- [x] Inspect parent evidence, approved SERVICE grants, event serializers and publication ownership.
- [x] Specify focused repairs, meaningful tests and guarded live verification.
- [ ] Implementation session: complete repairs, capture fresh verification and deploy to the existing test target.

## Analysis
- Preserve the existing bounded routes, scoped cursors, DTO alignment and reducer; the parent proof covers an injected callback, not composition-root authorization.
- Implement the approved minimum in proposal lines 194–196: monitoring-specific server-authenticated SERVICE principal, explicit synthetic-case grants and trusted document membership, including retained audit-only scope. Do not wait for an unspecified external provider: a shared module is already prescribed by the document-events follow-up.
- Wire both missing production dependencies in `main.py`: `lifecycle_authorize_read` and `lifecycle_audit_table`; the current audit listener is write-only configuration, not a read binding.
- Extend the existing event/store/reader chain for `ResultPublished` using publication brief 20 and the actual publish owner; preserve publication as an independent fact.
- Preserve parent evidence: `plans/checkpoints/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b.red-green-proof.md` has a genuine 403-versus-200 RED, but its callback GREEN is adapter-only; parent live ledger records zero cloud calls and historical NoCredentials.
- Use discovered `tdd` and `task-evidence` during implementation, `validate-implementation` after repair, and `save-learning` at completion. No PlantUML files were found; use the existing proposal and single OpenAPI contract.
- Apply recalled rules: canonical `attempt_no`, independent publication/terminal evidence, partial single-window semantics and source/image/live provenance. Recall used local backend, collection `wonderfulkb-learnings`, diagnostic `Collection not found`; prefer actual serializers over stale learning aliases.

## Approach
- Reuse or complete the shared `be-intake/app/processing_monitor_authorization.py` prescribed by the document-events follow-up; coordinate its public interface before editing to avoid duplicate authorization providers.
- Bind a dedicated server-only bearer credential to a SERVICE principal using a versioned Secrets Manager policy selected by `MONITOR_AUTH_SECRET_ARN`. Policy records contain credential SHA-256 digests, active/revoked state, principal type, exact case grants and explicit document scopes; reject malformed policy, wildcards, unknown credentials and client-supplied principal claims. Compare digests in constant time; fetch current policy with bounded timeout per request so revocation and rotation do not depend on stale allow caches.
- Retain existing intake `x-api-key` authentication and require the additional monitoring credential. The shared key alone never issues a scope. Store neither credential nor policy body in logs, responses or evidence; rotate by explicit active credential versions and revoke the old version with a readback check.
- Check grant before document lookup and audit Query. For current documents use consistent `docs.get_item` with the exact `(case_id, document_id)` key and validate returned scope. For retained audit-only documents require an explicit server-owned retained membership record with verified provenance in the policy; never derive membership from a token, audit scan or guessed ID. Use uniform masked 404 for ungranted/missing scope, 403 for invalid/unavailable SERVICE authorization, preserving no-store and zero audit reads.
- Compose the provider and configured audit table in `main.py`; absent/invalid auth configuration remains denied, absent audit configuration or failed authorized reads remains 503. Grant-source outages cannot fall back to cached grants or the shared intake key.
- Verify the producer-owned publication contract against `plans/tasks/2026-10-20_monitor-mvp-20-publication-events.md` and `be-document-processing/src/document_processing/pipeline.py:125–130`. Accept explicit events after the complete publish boundary; this repair delivers event persistence/read integration, not new worker hooks or a claim of live business publication.

## Implementation
1. Inspect current root and any component Git history/diffs and concurrent document-events authorization work; preserve all existing adapters, unrelated modifications and parent evidence. Use `task-evidence` to link the historical genuine RED with its limited adapter scope.
2. Add missing-boundary tests first using `tdd`; exercise real application construction with only Secrets Manager/DynamoDB clients replaced. Extend the existing `intake` fixture with opt-in configuration before import and a table registry; preserve its default upload tests. Do not install an authorization callback or patch `read_document` in the new composition/integration tests.
3. Implement the shared SERVICE provider and install it in `main.py`; create the read table from `AUDIT_TABLE_NAME` with bounded SDK settings, separate from the fail-open write listener. Package the new module in the existing Dockerfile. Test credential rotation/revocation, grant failure, current membership and retained scope before enabling successful requests.
4. Add frozen `ResultPublished` with envelope, `run_id`, positive `attempt_no`, `result_status=completed|partial|failed` and optional opaque `artifact_ids`; implement explicit allowlist serialization, Decimal-safe deserialization, conditional idempotent persistence and dispatch/type unions in `audit_queries.py` and `audit_storage.py`. Reject unsupported scope/status and content-bearing fields; keep event identity producer-supplied and never add business lookups/writes.
5. Reconcile publication identity explicitly: use the producer's stable `event_id` as `publication_id` when no separate publication identity exists, matching the reducer fallback; verify distinct StepFinished and publication IDs. Preserve evidence through actual store→reader→reducer→HTTP detail/audit, with partial publication leaving run state unknown absent RunFinished. Change reducer/OpenAPI only if focused contract tests expose an actual mismatch.
6. Add the dedicated secret reference and least-privilege GetSecretValue permission in `be-intake/template.yaml`; keep existing configuration and permissions intact. Document the policy schema, server-only transport, explicit synthetic grants and rotation procedure in `be-intake/README.md`. Use applicable AWS SDK/IAM/CloudFormation skills when implementing those changes.
7. Run the focused and regression gates below, build the existing linux/amd64 image, import installed modules as UID 10001, and record source file hashes plus build context/image digest; a Git HEAD alone cannot identify this modified workspace.
8. Authenticate through the supported AWS sign-in workflow, then inspect the actual eu-central-1 `wonderfulkb-ingest` App Runner ARN/account/ownership, current operation/revision, image digest and complete environment/secrets/IAM. Retain a retrievable previous image and protected recoverable config/secret version; verify both before rollout. Historical NoCredentials is not a current probe; a new authentication/permission failure is a real blocker for Jackie, not success.
9. Provision only explicit synthetic scopes backed by verified current or retained document membership. Reuse existing fixtures where entitled; ledger all new records. Bound this continuation to one candidate rollout plus one recovery, at most two synthetic document scopes, eight audit rows (including one isolated malformed decoder fixture), 24 live monitoring GETs, and zero business POST/model calls. Record control-plane calls separately; do not borrow/reset the Case Client budget or replay ambiguous writes. Conditional event IDs and secret revision guards prevent accidental overwrites.
10. Build/push the candidate through the existing target's supported workflow. Immediately recheck revision/operation and policy secret version before the in-place update; serialize this delivery and abort on drift. Preserve existing env/secrets/config while adding narrow monitoring settings. Wait boundedly for health, read back the deployed revision, resolved image digest, effective secret/config bindings and assert they match the candidate. Recovery may restore only this delivery's changes while revision still belongs to it.
11. Run direct authenticated HTTP assertions against the target: all three routes on the entitled fixture; known publication/event evidence; partial independent from terminal; limit=1 continuation on the same route; cross-operation/run/document/case cursor rejection; missing/forged SERVICE identity and ungranted scope denied before reads; no-store on every response. Use a separate explicitly granted synthetic malformed-event document to prove deployed decode/read failure returns safe 503, without breaking the shared table, changing IAM or adding a fault endpoint. Account for and retain/expire that labelled negative fixture under existing retention policy.
12. Write fresh checkpoint, RED/GREEN and live ledger under this task ID, linking the canonical plan. Include source→image→target provenance, verified recovery state, redacted policy version/principal/grant IDs, fixture records, request counts, assertions and blockers. Keep SOURCE/INSTALLED/DEPLOYED/LIVE-FUNCTION-VERIFIED distinct; do not close finding-003 with local tests. Run `validate-implementation`, then finish with `save-learning` and at least one saved learning.

## Testing
- From `be-intake`: `env PYTHONPATH=../be-document-processing/src ../be-document-processing/.venv/bin/python -m pytest -q tests/test_processing_monitor_lifecycle_views.py tests/test_processing_monitor_authorization.py`; include any existing shared-provider test module rather than duplicating it.
- From root: `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_publication_events.py be-document-processing/tests/test_monitor_audit_storage.py be-document-processing/tests/test_monitor_lifecycle_observations.py be-document-processing/tests/test_monitor_openapi_observation_contract.py`.
- Run all intake regressions and the existing audit-focused Python matrix; report pre-existing collection failures separately without deleting tests or weakening assertions. Run exactly `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` (registered gate, timeout 300 seconds).
- Assert one consistent bounded audit Query per authorized request, limit 1–100, and zero audit Query on invalid credentials, revoked/ungranted scope, forged membership or grant-source outage. Verify grant revocation on the next request, wrong-document denial, retained history with explicit membership, and publication-only/terminal-only fragments.
- Validate response DTOs against the single OpenAPI YAML; retain operation/case/document/run token binding, empty filtered continuation, partial coverage, safe 503 and no-store across 200/400/401/403/404/503. Spy on provider clients only; do not replace the reader in composition proof.
- Build with `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:lifecycle-ef257fc0 .`; verify installed imports as the runtime user, then record deployed HTTP bodies/assertions with credentials redacted. Health checks alone do not pass live acceptance.

## TDD
- Implementace TDD cyklu dle skill:tdd. Preserve and link the parent's genuine RED at `plans/checkpoints/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b.red-green-proof.md`; do not recreate a failing implementation for already completed adapters. Capture new RED only for still-missing composition/publication behavior, followed by fresh GREEN under `task-ef257fc0-2159-4888-983a-0b30a1dbfe39` with identical focused argv per capture.
- Append this executable pytest skeleton to `be-intake/tests/test_processing_monitor_lifecycle_views.py` using the existing imported `intake` fixture; it fails on actual missing composition, not a missing import. Extend it with the configured client-backed 200 tests from Implementation step 2 before claiming the authorization fix.

```python
def test_composition_installs_real_lifecycle_authorizer(intake):
    main, *_ = intake
    provider = getattr(main.app.state, "lifecycle_authorize_read", None)
    assert callable(provider)  # RED: main.py currently installs no provider
```

- Create `be-document-processing/tests/test_monitor_publication_events.py` with existing reader imports; this executable skeleton fails on unsupported dispatch, then add real ResultPublished→AuditStore→DynamoDB round-trip, duplicate, invalid-field and three-status cases before implementation.

```python
from unittest.mock import Mock
from document_processing.audit.audit_queries import read_document

def test_bounded_reader_decodes_partial_publication():
    row = dict(schema_version=1, case_id="case-test", document_id="doc-test",
               event_id="publication-1", sequence=1, type="ResultPublished",
               occurred_at="2026-10-20T10:00:00Z", run_id="run-1",
               attempt_no=1, result_status="partial", artifact_ids=["artifact-1"])
    table = Mock()
    table.query.return_value = {"Items": [row]}
    page = read_document(table, "case-test", "doc-test", limit=1)
    assert page.items[0].to_item() == row
    assert table.query.call_count == 1
```

| Test | Genuine RED / inherited proof | Fresh GREEN required |
|---|---|---|
| Composition skeleton | Installed provider is absent | Provider composed from real configuration; no test callback |
| SERVICE HTTP integration | New configured request denied by missing provider/table | Real credential→grant→membership→reader yields runs/detail/audit 200 |
| Publication reader skeleton | Unsupported audit event type | Exact publication round-trip and one bounded Query |
| Store→HTTP partial publication | Publication dispatch absent | Stable publication identity/evidence, no inferred run terminal |
| Existing adapter/cursor cases | Link parent genuine RED, do not replay | Fresh GREEN plus denial-before-read matrix |

## Files
- `be-intake/app/processing_monitor_authorization.py`: shared credential/policy/grant/membership adapter; reuse concurrent implementation if present.
- `be-intake/app/main.py`, `processing_monitor_lifecycle_routes.py`, `Dockerfile`: composition, shared scope compatibility and packaging; preserve working bounded handlers.
- `be-intake/template.yaml`, `be-intake/README.md`: dedicated secret binding, narrowly scoped access and operational schema/rotation documentation.
- `be-intake/tests/test_monitor_file_received.py`, `test_processing_monitor_lifecycle_views.py`, `test_processing_monitor_authorization.py`: opt-in fixture configuration and real-boundary integration/denial coverage.
- `be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`, `audit_queries.py`: publication contract, persistence types and dispatch; `audit_lifecycle_observations.py` only for a verified mapping gap.
- `be-document-processing/tests/test_monitor_publication_events.py`, `test_monitor_openapi_observation_contract.py`, `contracts/openapi-processing-monitor.yaml`: publication round-trip and precise contract parity where needed.
- `plans/checkpoints/task-ef257fc0-2159-4888-983a-0b30a1dbfe39.checkpoint.md`, `plans/checkpoints/task-ef257fc0-2159-4888-983a-0b30a1dbfe39.red-green-proof.md`, `plans/monitoring/task-ef257fc0-2159-4888-983a-0b30a1dbfe39-lifecycle-http-evidence.md`: new implementation evidence; link this plan in the checkpoint/state without editing task storage manually.
