# Lifecycle HTTP repair evidence — task-ef257fc0-2159-4888-983a-0b30a1dbfe39

## Delivery state

**SOURCE: implemented. INSTALLED: verified in local linux/amd64 image.
DEPLOYED: blocked. LIVE-FUNCTION-VERIFIED: not performed.**

Authority: `plans/2026-10-20_task-ef257fc0-2159-4888-983a-0b30a1dbfe39_acceptance-fix-monitoring-lifecycle-http-skute-n-bounded.md`.
No plan was edited. Existing workspace changes and historical evidence preserved.

## Authorization and publication

- `main.py` installs `ServiceDocumentAuthorizer` and the bounded read table using
  `MONITOR_AUTH_SECRET_ARN` and `AUDIT_TABLE_NAME`; intake key remains required on
  lifecycle runs/detail/audit. Missing configuration denies without audit reads.
- Concurrent document-events work added the shared `AuthorizationSecretSource`,
  case/membership helpers and middleware during this session. Lifecycle policy is
  normalized through those helpers with an exact credential-specific document
  allowlist. Lifecycle bypasses the document-events middleware preflight so its
  additional key requirement and safe 403 semantics remain intact.
- Current document membership is a consistent exact-key GetItem. Retained
  membership requires a server-attested scope and an absent current row; a forged
  current row cannot be overridden by retained provenance. The normalization's
  retained scopes are isolated per credential, including during rotation.
- Tests replace only AWS clients. Real composition, store, decoder, reducer and
  HTTP adapters execute; no injected authorization callback or reader substitute
  is used in the new composition tests.
- `ResultPublished` carries producer-supplied event/run/attempt identity,
  completed/partial/failed result status and optional opaque artifact IDs. Frozen
  allowlisted serialization, Decimal readback and conditional duplicate handling
  use the existing audit store. Publishing steps and safe failure code supported.
- Actual producer reference `pipeline.py:125–130` validates the result, writes S3,
  updates the owned job and updates the document. No business publication hook is
  claimed. Explicit publication events are accepted only as producer observations.
- The actual reducer lacked the fallback assumed by the plan. Integration exposed
  empty published_results after successful decoding; it now uses event_id when
  ResultPublished has no separate publication_id. StepFinished remains distinct;
  partial publication leaves run state unknown without RunFinished.

## Genuine TDD provenance

Canonical proof: `plans/checkpoints/task-ef257fc0-2159-4888-983a-0b30a1dbfe39.red-green-proof.md`.
Read back after final GREEN. All phases captured by discovered
`/Users/michal/.config/opencode/skills/tdd/scripts/proof-capture.py`; no manual proof edits.

Exact focused command in both cycles:

```sh
env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_authorization.py be-document-processing/tests/test_monitor_publication_events.py
```

- Initial RED `610c11f1be504901a4922455e7a67a46`: accepted_red, child exit 1;
  missing composition provider, expected 200 versus actual 403, unsupported event.
- Initial GREEN `086dc22781e243c597ce4599a843daed`: accepted_green, 21 passed.
- Initial complete cycle retained by helper at
  `plans/checkpoints/task-ef257fc0-2159-4888-983a-0b30a1dbfe39.cycles/cycle-70abe1f13fb04f8c9690f1557ce1b8fe.md`.
- New regression RED `c446f4ad374649c98b92e25ba08a7536`: accepted_red,
  1 failed / 21 passed; another credential's retained grant produced 200 instead
  of 404 for a missing current document. Captured before fixing the normalizer.
- Isolation GREEN `5a87993b83384c33b3ff58ea63ee5769`: accepted_green, 22 passed,
  child exit 0 with identical argv.
- Isolation cycle archived at `plans/checkpoints/task-ef257fc0-2159-4888-983a-0b30a1dbfe39.cycles/cycle-a7c06f7353204c41bab4b7057a574b46.md`.
- Final masked-case RED `0396a555439044d3a6b1e22e4f1a03fa`: accepted_red,
  1 failed / 22 passed; valid identity with no case grant returned 403 instead
  of the plan's uniform masked 404. Captured before adding lifecycle-specific
  `mask_ungranted`; document-events default behavior preserved.
- Final GREEN `7b52b5a0adfd4cd5a752d741071a760c`: accepted_green, 23 passed,
  child exit 0 with identical focused argv. Canonical proof now contains this cycle.
- Rejected GREEN attempts `640331091b84402fb65c04edd6197ec1`,
  `1dbb6c8faeea44d58426cad8feedf1a5`, `03a054a2068c4f19867803bb7871113d`
  remain diagnostic history in `.tdd-test-runs/`; none was relabelled successful.

Parent genuine adapter RED remains at
`plans/checkpoints/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b.red-green-proof.md`.
`task-evidence` generated
`plans/checkpoints/task-4f189265-c034-43e8-b8d9-c4e1fef9a45b.evidence.md`.
Its exact historical command
`env PYTHONPATH=../be-document-processing/src ../be-document-processing/.venv/bin/python -m pytest -q tests/test_processing_monitor_lifecycle_views.py tests/test_monitor_file_received.py`
records `11 passed, 1 warning in 0.30s`. Extracted historical helper commands have
`outcome_unavailable` and `command_lines_truncated`; parent lineage also reports
`outcome_lines_truncated`. Do not reconstruct those missing historical lines.

## Verification commands and actual outcomes

| Working directory | Command | Outcome |
|---|---|---|
| be-intake | `env PYTHONPATH=../be-document-processing/src ../be-document-processing/.venv/bin/python -m pytest -q tests` | 64 passed, 2 failed: older pages/steps tests expect 200 with only x-api-key, concurrent middleware returns 403 |
| be-intake | `env PYTHONPATH=../be-document-processing/src ../be-document-processing/.venv/bin/python -m pytest -q tests/test_processing_monitor_lifecycle_views.py tests/test_processing_monitor_authorization.py tests/test_monitor_file_received.py tests/test_processing_monitor_routes.py` | 59 passed after normalization repair; 60 passed after final masked-case repair |
| root | `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_publication_events.py be-document-processing/tests/test_monitor_audit_storage.py be-document-processing/tests/test_monitor_lifecycle_observations.py be-document-processing/tests/test_monitor_openapi_observation_contract.py` | 70 passed |
| be-document-processing | `env PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_monitor_*.py` | 177 passed |
| root | `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` | 17 passed; bundled 5 functions |
| root | `uvx --from cfn-lint cfn-lint be-intake/template.yaml` | exit 0, including final template context change |
| root | `git diff --check` | exit 0 |
| root | `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:lifecycle-ef257fc0 .` | exit 0; rebuilt after final auth repair |

Installed container command used `docker run --rm --platform linux/amd64 --user
10001` with synthetic import-only API_KEY/RAW_BUCKET, AWS metadata disabled and
eu-central-1. Actual main, provider, event, store and reader imports succeeded;
assertions confirmed UID 10001 and installed callable provider. No AWS calls
were made by these imports. Hashes below came from installed container files,
matching the host `shasum -a 256` output byte for byte.

## Candidate source → image provenance

- Build context: repository root `/Users/michal/Projects/wonderfulkb`, Dockerfile
  `be-intake/app/Dockerfile`; existing modified workspace, not just Git HEAD.
- Git baseline inspected: `fd8cab7` (existing root HEAD); no commit created.
- Final local OCI index/image ID:
  `sha256:f0d5be046b01c9046405783a494e8bc3e77cc45207eeae29c70f787f94194570`.
- Final linux/amd64 manifest:
  `sha256:5e4a10cd7243157443e26474a2d0c407e242bebb33def41ef0ae232484a35494`.
- Final config digest:
  `sha256:71e68b6b8e857c40c64c1a1e1869b2a4f3db78073e488d0930874228c7f6f422`.
- Prior local build `sha256:270748dabb10c9839090e6a58eb544c6d13fa1500cbfc9b2a827b770c9327ab1`
  was superseded after the final masked-case repair; neither image was deployed.
- `docker image inspect` confirms `amd64 linux app`; runtime numeric UID checked.
- No ECR push occurred. These are local artifact identities, not deployed digests.

| Source path | SHA-256 (also verified installed where applicable) |
|---|---|
| be-intake/app/main.py | f72242d6e21e97553420ceda4af8e8abc3e5f5ce868308f809c2a4148f2db0d1 |
| be-intake/app/processing_monitor_authorization.py | 5527838db9e75a0aa1c721a7d2c46c62f81a115778c8b867c0e215291df5b96a |
| be-intake/app/processing_monitor_lifecycle_routes.py | cc712b8d095a2c41b87d76229be4a2d2127ae99b319a56674c0d59578797d0fe |
| be-intake/app/processing_monitor_routes.py | 92b0152ceb0f0d881e0c9011c63b6d4ab5e04e58577c258f6c6cf4aae9caa861 |
| be-document-processing/src/document_processing/audit/audit_events.py | 3c8007b44e59bee2581be718d639d7cc8c20bd5836d176bc919b37978c637960 |
| be-document-processing/src/document_processing/audit/audit_storage.py | 113b40ce67095016f3d496329ed2bd949c12963033c2010e975a7660db0d73ba |
| be-document-processing/src/document_processing/audit/audit_queries.py | db56ce0be958a19185f4c044d179db3ecf78a7281589061cc5fa46589ae49304 |
| be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py | d35d87e36a5b317ec286c37d562fba95bd78ec097c4a9fd3503eb223da047a5b |
| be-intake/app/Dockerfile (host only) | a5a50b1b87749163d34373a3b0b2065bd5ad4db10a71e2ed57b81b92153d37ff |
| be-intake/template.yaml (host only) | 0e5851bed69c6ac7c0626589b34654e2f582e13beb485870183d9e3b0de08cd5 |

## AWS authentication, recovery and fixture ledger

Fresh local-shell probe: `aws --version && aws sts get-caller-identity`:
`aws-cli/2.38.1 Python/3.15.0 Darwin/24.6.0 source/arm64`, then
`NoCredentials: Unable to locate credentials ... aws login`.
This is a fresh blocker, not reliance on parent history. `signing-in-to-aws`
requires explicit confirmation before invoking interactive `aws login`; it was
not invoked without confirmation. Jackie owns operational continuation when
this agent cannot authenticate.

| Item | Actual status/count |
|---|---|
| Authentication probe | 1 failed STS command; no usable credentials |
| Signed target control-plane requests | 0 |
| Target account / App Runner ARN / ownership / revision / operation | NOT VERIFIED |
| Existing target image / environment / secret versions / IAM | NOT VERIFIED |
| Retrievable previous image and protected recovery config/policy | NOT VERIFIED; rollout cannot start |
| Synthetic case/document records | 0 created, 0 modified |
| Synthetic audit rows, including malformed fixture | 0 written |
| Secret/policy writes or rotations | 0 |
| Candidate rollouts / recoveries | 0 / 0 |
| Live monitoring HTTP GETs | 0 / 24 budget |
| Business POSTs / model calls | 0 / 0 |
| Case Client fixture/budget use | 0 |

No live principal/grant IDs or fixture entitlement is asserted. Synthetic test
IDs above are local-only. No live HTTP bodies/assertions exist for this task.
finding-003 remains OPEN. Resume only after supported authentication, inspect
the actual eu-central-1 wonderfulkb-ingest target, secure and verify its recovery
artifact/configuration, recheck source hashes and serialized revision/secret
guards, then use the original one-candidate/one-recovery, two-document,
eight-audit-row, 24-GET budget. Preserve the malformed fixture's labelled ledger
and test all required cursor scope, denial, no-store and safe-503 assertions.

## Validation limitations

`validate-implementation` loaded. Its workflow/rules reference reads were denied
by the harness external-directory policy, as were deeper AWS SDK/IAM/CFN
references; no alternative access bypass was attempted. Source/contract/test
validation above was performed directly against the authoritative plan. No
PlantUML changes or business table schema changes were needed. Overall plan
completion remains blocked on live deployment evidence, not marked complete.
