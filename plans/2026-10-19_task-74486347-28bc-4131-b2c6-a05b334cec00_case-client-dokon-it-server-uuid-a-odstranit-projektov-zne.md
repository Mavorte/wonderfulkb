# Plan 2026-10-19: Case Client server UUID and acceptance diff hygiene

## Progress

- [x] Initialize canonical plan path.
- [x] Inspect requirements, source, docs and learnings.
- [x] Specify implementation, TDD evidence and verification.
- [x] Correct canonical plan header after invalid_header recovery.
- [x] Incorporate expanded host-authored ignore policy and isolated acceptance-diff verification without implementing source changes.

## Analysis

- `be-case-client/src/case_client_handler.py` currently requires caller `case_id` and chooses 201/200; `case_client_repository.py`, mock and DynamoDB adapter still expose `(case_id, client_id, metadata)` and replay existing keys.
- Existing `test_case_client_lambda.py::CaseClientLambdaTests.test_post_generates_new_uuid_and_ignores_supplied_case_id` is already a targeted RED; other replay/validation tests and DynamoDB Stubber fixtures must be migrated, not discarded.
- Existing OpenAPI labels 1.4.0 and describes UUID create, but runtime contradicts it; preserve `CaseDetails` expansion while reconciling spec and dated deployed-status caveat.
- Read-only manifest pins 28 snapshots to commit `88c04ee6e850c147ffeba46fe626bb0acd4863f3`; integrate manifest-listed docs selectively and never edit handoff snapshots.
- Root `.gitignore` already has host-authored broad build/cache/local rules (including SAM, both frontend dist trees, runner-dist, node_modules symlinks, Python outputs, test caches/logs and `.env` example exceptions); preserve this exact work. Host-local excludes can mask root behavior, so validate against an isolated fixture.
- `learnings/architecture/2026-10-19_case-client-source-contract-vs-deployed-state.md`: separate source UUID contract from dated deployed status; bounded collision retries and strong readback. `learnings/runtime-errors/rules-case-client-dynamodb-decimal-range.md`: reject out-of-range Decimal before SDK; retain exact numeric JSON. `learnings/architecture/decisions-case-client-backend-static-invariants.md`: mock must never load SDK and SAM policy branches remain covered; mock state stays instance-local.
- `docs/quick-connect.md` exists only in the pinned handoff and must be integrated at its destination as a dated deployment note. No PlantUML diagram found. Discovered skills: `tdd` for new root proof; `code-review` and `write-review-report` for independent review; `save-learning` after main work.
- `learnings/tooling/rules-case-client-source-contract-and-acceptance-noise.md`: distinguish source 1.4.0 from deployed behavior, capture fresh root-specific RED/GREEN after dependency check, and isolate ignore validation from host excludes. `recall-knowledge` discovery used local fallback (missing `wonderfulkb-learnings` collection).

## Approach

- Make repository create accept `(client_id, metadata)` and return the created case; generate UUIDv4 per attempt in each adapter, ignore caller `case_id` entirely at the handler (even malformed values), return 201 for every success. Keep GET path validation, public field projection, client 404/inactive-or-blocked 409, malformed client/metadata 400, sanitized operational 500.
- DynamoDB: validate metadata/client before SDK, strong-read client and require active; for at most **three distinct generated IDs**, transact `ConditionCheck` of active client plus `Put` guarded by `attribute_not_exists(case_id)`. On `TransactionCanceledException` only `[None, ConditionalCheckFailed]` denotes a possible case-key collision: strong `GetItem` on generated case key; if occupied, discard it and generate a fresh ID, otherwise fail sanitized 500 (ambiguous cancellation). `[ConditionalCheckFailed, None]` requires strong client re-read and mapping to 404/409 if missing/nonactive; active/ambiguous state fails 500. Missing/mixed/unknown reason codes or simultaneous failures fail 500 without retry. Exhausted occupied-key attempts fail 500; never return or overwrite occupant. Other SDK failures fail 500 without retry. Keep strong GET-by-ID and Decimal metadata handling.
- Mock: lock around active-client check and insert; generate fresh UUIDv4, guard existing fixture/generated keys with bounded attempts and fail safely on exhaustion; return independent deep copies. Keep one execution environment's state separate from new instance fixtures.
- Reconcile pinned read-only handoff into current files by selective edits; retain expanded `CaseDetails` separately from this create-contract change (record ambiguity without implementing details). Do not add GET `/cases`.

## Implementation

1. Verify `/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python` reports 3.13.7 and imports `boto3`, `botocore`, `simplejson` with fake credentials, `AWS_EC2_METADATA_DISABLED=true` and no network. Unexpected interpreter/dependency failure is a blocker, not RED. Use `skill:tdd` proof capture with **task-74486347-28bc-4131-b2c6-a05b334cec00**, recording the existing assertion RED before editing implementation; never alter previous root proof or helper. Before touching source, use the same exact focused argv for RED and GREEN.
2. Migrate `CaseClientLambdaTests` replay, inactive-precedence, invalid-body, deep-copy/concurrent, event, and GET tests to new IDs and statuses without losing original regression intent; add omitted ID, arbitrary caller ID, two identical POSTs, UUIDv4, blocked/missing client and metadata cases. Update shared protocol, handler and mock; retain fail-closed configuration, no-SDK mock guarantee and response projection.
3. Migrate existing DynamoDB Stubber helpers/cases to deterministic UUID injection and exact request matching. Cover ordinary handler create and GET of returned ID, repeated create, strong reads, both transaction condition positions, collision recovery and third-collision exhaustion; assert all stub responses consumed, no overwritten/returned occupant, Decimal bounds and sanitized SDK errors. Implement bounded adapter flow without adding parallel DB paths.
4. Align `be-case-client/openapi-case-client.yaml` (1.4.0 and existing `CaseDetails` retained), `events/create-case.json`, component README files and remote docs with implemented source semantics. Keep quick-connect deployed behavior as dated observation; do not conflate OpenAPI 1.4.0 with runtime or deployment proof.
5. Preserve host-authored root `.gitignore` as the permanent project ignore policy; inspect rule coverage for SAM, both frontend `dist`, `app/dist` and `app/runner-dist`, root app dist packages, node_modules including symlinks, Python caches/venvs/packaging, coverage/temp/logs, local env with visible `.env.example`/`.sample`/`.template`, OS/editor caches. Make only narrowly necessary additions if gaps remain; leave nested `.gitignore` and build scripts untouched. Do not ignore source, templates, tests, plans/proofs/handoffs, proposals, Markdown, OpenAPI, manifests, lockfiles or `opencode.json`; do not delete generated artifacts or modify `.git`/index/branches/commits.

## Testing

- Focused RED/GREEN: same exact argv from repository root, `PYTHONPATH=be-case-client/src AWS_EC2_METADATA_DISABLED=true AWS_ACCESS_KEY_ID=offline AWS_SECRET_ACCESS_KEY=offline /Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m unittest discover -s be-case-client/tests -p 'test_case_client_lambda.py' -k test_post_generates_new_uuid_and_ignores_supplied_case_id -v`; RED must contain real 201-vs-200 assertion and GREEN must pass using `skill:tdd` proof capture in this task's checkpoint. Extend Stubber tests after captured RED; do not reuse prior proof.
- Whole suite: `PYTHONPATH=be-case-client/src AWS_EC2_METADATA_DISABLED=true AWS_ACCESS_KEY_ID=offline AWS_SECRET_ACCESS_KEY=offline /Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m unittest discover -s be-case-client/tests -p 'test_*.py' -v`; syntax: `/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python -m compileall -q be-case-client/src be-case-client/tests`; offline `sam validate --lint --template-file be-case-client/template.yaml`; registered gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`. Record real failures rather than suppressing them; no AWS/HTTP/deploy.
- Check root ignore in a temporary isolated fixture/repository containing **only copied root `.gitignore`**, without local/global excludes (set isolated Git config); check representative paths in every generated category above including symlinked `node_modules`, and negative paths for source, fixtures, `.env` examples, templates, tests, plans/proofs/handoffs, proposals, Markdown, OpenAPI, manifests, lockfiles and `opencode.json`. No test may mutate this repo's index or `.git` metadata; inspect `git ls-files` read-only for already tracked generated files before reporting scope.
- Review `git status --short`, `git diff --stat`, `git diff`, `git ls-files --others --exclude-standard` and scoped source diff covering `<base>..HEAD` plus working, staged and untracked paths; account for pre-existing user work, verify handoff SHA256 unchanged and output not truncated at 120000 chars / 500 paths. Obtain independent semantic review with `skill:code-review` and finish its review phase with `skill:write-review-report`; report actual changed paths, exact verification outcomes and unresolved findings. No source-only claim of deployed success.

## TDD

- Test file: `be-case-client/tests/test_case_client_lambda.py`; framework `unittest`; existing executable RED skeleton below is **already in file** (imports `unittest`, `UUID`, fixture `ACTIVE` and `CaseClientLambdaTests` above it), so keep it intact until proof is captured. Implementace TDD cyklu dle skill:tdd. Use the **same focused command** in Testing for RED and GREEN.

```python
def test_post_generates_new_uuid_and_ignores_supplied_case_id(self):
    body = {'client_id': ACTIVE, 'case_id': 'caller-controlled', 'metadata': {}}
    first = self.invoke('POST', '/cases', body=body, expected=201)
    second = self.invoke('POST', '/cases', body=body, expected=201)
    self.assertNotEqual(first['case_id'], second['case_id'])
    for result in (first, second):
        parsed = UUID(result['case_id'])
        self.assertEqual(parsed.version, 4)
        self.assertEqual(result['status'], 'open')
```

| Test | RED | GREEN |
|---|---|---|
| `CaseClientLambdaTests.test_post_generates_new_uuid_and_ignores_supplied_case_id` | Second POST yields 200 instead of asserted 201 (current replay) | Both return 201, distinct UUIDv4, caller ID ignored |
| Added omitted-ID mock + DynamoDB Stubber tests | Handler returns 400 / adapter expects caller ID | 201 with persisted UUID and strong GET |
| Migrated collision/reason tests | Old adapter returns existing case/200 or maps owner conflict | Precise reason-code classification, bounded retry, exhaustion 500, no occupant exposed |

## Files

- Source: `be-case-client/src/case_client_handler.py`, `case_client_repository.py`, `case_client_mock_repository.py`, `case_client_dynamodb_repository.py`; tests: `be-case-client/tests/test_case_client_lambda.py`, `test_case_client_dynamodb_repository.py`, `test_case_client_template.py` only if needed for existing policy coverage; contract: `be-case-client/openapi-case-client.yaml`, `be-case-client/events/create-case.json`, `be-case-client/{README.md,src/README.md,tests/README.md,events/README.md}` as needed.
- Repo config: existing host-authored `.gitignore` (preserve; narrow edits only if a demonstrated coverage gap); current dedicated plan and new task-specific proof/checkpoint under `plans/`; never alter historical proof, handoff snapshots, or task lifecycle storage.
- Manifest-listed incoming documentation paths (review each; edit selectively as required): `apps/README.md`, `apps/backoffice/README.md`, `be-case-client/README.md`, `be-case-client/events/README.md`, `be-case-client/src/README.md`, `be-case-client/tests/README.md`, `be-intake/app/README.md`, `be-intake/documents-table/README.md`, `design-system/README.md`, `design-system/assets/README.md`, `design-system/fonts/README.md`, `docs/README.md`, `docs/proposals/README.md`, `docs/quick-connect.md`, `learnings/README.md`, `learnings/architecture/README.md`, `learnings/runtime-errors/README.md`, `learnings/tooling/README.md`, `plans/README.md`, `plans/case-client-aws.md`, `plans/checkpoints/README.md`, `plans/tasks/README.md`. Other manifest entries are component code/tests/event/OpenAPI references, not permission to change other apps.
