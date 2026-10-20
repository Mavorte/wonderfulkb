# Plan: Trigger template parity and rollback path

Restore the trigger's reference to the canonical documents-table template and ensure its stream-enabled copy preserves canonical resources, safety properties, and outputs.

## Analysis

- Canonical owner: `be-intake/documents-table/template.yaml`; the trigger's root-level `documents-table/template.yaml` reference is absent.
- The canonical template contains `DocumentsTable` and `AuditTable`; parity must cover both resources and all canonical outputs.
- Normalize only `DocumentsTable.Properties.StreamSpecification`; permit only `StreamArn` as an additional output.
- The rollback reference must resolve from `be-validator-agent/trigger/deploy.sh` to the canonical owner.
- Prior focused host run at `/tmp/wkb-test-0909/trigger-supported.log` reported `FileNotFoundError`; treat it as failed evidence, not a pass.
- Learning `learnings/architecture/2026-10-20_stream-template-parity-preserves-audit-resources.md`: preserve complete resource/output parity and resolve rollback paths from the script location.

## Approach

1. Change the test's canonical reference to `be-intake/documents-table/template.yaml` and make its parity assertion compare complete resources after removing only the stream specification from the stream variant's `DocumentsTable`.
2. Assert canonical outputs are all retained; allow only the intentional `StreamArn` addition.
3. Synchronize the stream template with all canonical resource and output definitions, retaining AuditTable, retention, PITR, tags, encryption, and current outputs.
4. Correct `ORIGINAL_TEMPLATE` in `deploy.sh` to point to the canonical owner using a path anchored to the script directory.

## Implementation

- Inspect existing working-tree changes before editing and preserve unrelated work.
- Update the regression test first; run it with the exact focused argv and capture genuine RED evidence.
- Update the stream template and rollback path; rerun focused tests for GREEN.
- Keep the canonical template's business schema unchanged; perform no AWS operations or data/table changes.

## Testing

- From `be-validator-agent/trigger`, run `../../be-document-processing/.venv/bin/python -m pytest -q tests/test_template.py` before and after implementation; record the initial failure accurately.
- Run the full trigger suite with the same interpreter.
- Run registered gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- Offline-check rollback path resolution from the trigger directory and from the script's own location.
- Run available CloudFormation validation or `cfn-lint` against both canonical and stream templates; report unavailable tooling explicitly.
- No deployment or live AWS validation.

## TDD

**Test file:** `be-validator-agent/trigger/tests/test_template.py`
**Framework:** pytest; existing focused test exercises YAML-template parity.
**Run command (from `be-validator-agent/trigger`):** `../../be-document-processing/.venv/bin/python -m pytest -q tests/test_template.py`
**Edit hint:** Update `test_stream_copy_of_the_table_template_differs_only_by_the_stream`.

```python
from pathlib import Path
import yaml

def test_stream_copy_of_the_table_template_differs_only_by_the_stream():
    root = Path(__file__).resolve().parents[3]
    canonical = yaml.safe_load((root / "be-intake/documents-table/template.yaml").read_text())
    stream = yaml.safe_load((Path(__file__).resolve().parents[1] / "documents-table-with-stream.yaml").read_text())
    assert set(stream["Resources"]) == set(canonical["Resources"])  # RED: current stream copy omits AuditTable
    assert set(canonical["Outputs"]).issubset(stream["Outputs"])  # RED: canonical audit outputs are missing
    assert set(stream["Outputs"]) - set(canonical["Outputs"]) <= {"StreamArn"}
```

| Test assertion | RED before implementation | GREEN after implementation |
|---|---|---|
| Resource keys match | Missing `AuditTable` in stream copy | All canonical resource keys retained |
| Canonical outputs retained | Missing canonical outputs | All canonical outputs retained; optional `StreamArn` only |
| Normalized resource bodies match | Any non-stream business/safety drift fails | Only stream specification differs |

Implement the TDD cycle using `skill:tdd`; compare normalized resources, not merely key sets, and retain the existing test's precise stream-property checks.

## Files

| File | Planned change |
|---|---|
| `be-validator-agent/trigger/tests/test_template.py` | Use canonical owner path; assert full normalized resource and output parity. |
| `be-validator-agent/trigger/documents-table-with-stream.yaml` | Restore AuditTable and all canonical settings/outputs while retaining stream configuration and permitted `StreamArn`. |
| `be-validator-agent/trigger/deploy.sh` | Resolve `ORIGINAL_TEMPLATE` to the canonical owner relative to the script location. |

## Progress

- [x] Determine mandatory canonical plan path and load relevant parity learning.
- [ ] Implement test-first change and capture RED.
- [ ] Synchronize template and rollback reference; verify GREEN and all specified gates.
