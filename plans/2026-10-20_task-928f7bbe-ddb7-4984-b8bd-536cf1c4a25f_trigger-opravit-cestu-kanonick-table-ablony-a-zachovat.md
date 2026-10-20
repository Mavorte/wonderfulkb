# Plan: Repair trigger template acceptance gaps

Repair the script-directory rollback path and produce valid follow-up verification without repeating the completed stream-template parity work.

## Analysis

- `deploy.sh` changes directory to its own directory, but `ORIGINAL_TEMPLATE` currently resolves from the process working directory; explicitly anchor it to `BASH_SOURCE[0]`.
- `tests/test_template.py` now uses `HERE.parents[1]` and passes parity assertions; preserve this work.
- Parent RED evidence is invalid because it failed during path lookup. Do not relabel it or fabricate historical RED; use the genuine historical evidence if located in parent lineage and capture fresh GREEN for this task.
- Learning `learnings/architecture/2026-10-20_trigger-stream-template-canonical-parity.md` confirms repository-root indexing and script-relative rollback resolution.

## Approach

1. Inspect parent-task proof/checkpoint provenance and identify any genuine pre-implementation RED that reached the parity assertions; link it as historical evidence only if verified.
2. Add a focused regression check for `ORIGINAL_TEMPLATE` being derived from the deploy script directory, including invocation from a different working directory.
3. Run the focused regression before implementation and capture RED, then anchor the shell path using `BASH_SOURCE[0]` and rerun for GREEN.
4. Run focused template tests and the registered backoffice test/build gate; record any pre-existing failures distinctly.

## Implementation

- Preserve existing stream-template and parity changes; do not rewrite completed behavior.
- Derive `SCRIPT_DIR` from the resolved location of `${BASH_SOURCE[0]}` and construct `ORIGINAL_TEMPLATE` from it.
- Ensure the path test runs without AWS calls, changing directory to an unrelated temporary/current directory and checking the canonical template path.
- Maintain accurate task-scoped RED/GREEN proof and reference historical RED without editing its evidence.

## Testing

- Focused trigger parity/path tests from `be-validator-agent/trigger` using `../../be-document-processing/.venv/bin/python -m pytest -q tests/test_template.py`.
- Exercise path resolution when launched outside the trigger directory; assert the result points to `be-intake/documents-table/template.yaml`.
- Run full trigger suite and report existing unrelated failures accurately.
- Run registered gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- No deployment or AWS operations.

## TDD

**Test file:** `be-validator-agent/trigger/tests/test_template.py`  
**Framework:** pytest; existing template contract tests use this file.  
**Run command (from `be-validator-agent/trigger`):** `../../be-document-processing/.venv/bin/python -m pytest -q tests/test_template.py`  
**Edit hint:** Add a regression assertion/test for script-relative canonical rollback path.

```python
from pathlib import Path
import subprocess

def test_deploy_rollback_template_path_is_script_relative():
    script = HERE / "deploy.sh"
    unrelated_cwd = HERE.parent
    # RED: current ORIGINAL_TEMPLATE is evaluated from the process cwd.
    result = subprocess.run(
        ["bash", "-c", 'source <(sed -n "/^ORIGINAL_TEMPLATE=/p" "$1"); printf "%s" "$ORIGINAL_TEMPLATE"', "bash", str(script)],
        cwd=unrelated_cwd, capture_output=True, text=True, check=True,
    )
    assert Path(result.stdout) == HERE.parents[1] / "be-intake/documents-table/template.yaml"
```

The implementation may use a safer non-executing extraction strategy for the test if sourcing deploy.sh would trigger AWS initialization; test only the path expression, never execute deployment actions.

| Test | RED before implementation | GREEN after implementation |
|---|---|---|
| Script-relative canonical path | Resolves from unrelated caller directory or fails | Resolves to canonical template regardless of caller cwd |
| Template parity regression | Historical genuine RED only if verified in parent lineage; otherwise no fabricated RED | Existing complete resource/output parity assertions pass |

Implement the TDD cycle using `skill:tdd`; retain the failed path-index artifact as invalid evidence and capture fresh task-scoped proof.

## Files

| File | Change |
|---|---|
| `be-validator-agent/trigger/deploy.sh` | Anchor canonical rollback template path to script location. |
| `be-validator-agent/trigger/tests/test_template.py` | Add caller-working-directory-independent path regression coverage. |
| `be-validator-agent/trigger/plans/checkpoints/task-928f7bbe-ddb7-4984-b8bd-536cf1c4a25f.red-green-proof.md` | Record genuine task-scoped RED/GREEN and link verified historical evidence. |

## Progress

- [x] Load acceptance findings, original plan, current code, and parity learning.
- [x] Resolve canonical plan path and inspect parent proof artifact.
- [ ] Verify parent-lineage genuine RED provenance and add focused regression test.
- [ ] Correct script-relative path and capture fresh GREEN plus required gates.
