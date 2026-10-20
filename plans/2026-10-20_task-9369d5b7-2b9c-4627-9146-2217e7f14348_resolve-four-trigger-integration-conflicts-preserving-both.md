# Plan: Resolve four trigger integration conflicts preserving both features

Mechanically resolve the four specified conflict regions as a semantic union, then run only the prescribed offline checks and trigger test suite.

## Analysis

- Scope is limited to the four files under `be-validator-agent/trigger/` named in the request.
- Preserve upstream case lifecycle/webhook paths and local execution/audit paths; remove conflict markers without changing unrelated behavior.
- Existing Python tests and the virtual environment are available under `be-validator-agent/trigger/`.
- No project documentation or architecture changes are required for this bounded conflict resolution.

## Approach

- Apply the supplied exact `build.sh` copy lists and audit directory synchronization.
- In `common.py`, retain all initializations and add the specified cases, execution, and lazy audit accessors with correct indentation/decorators.
- In `template.yaml`, retain both sides of all three conflicts with valid YAML indentation and preserve unrelated resources/environment settings.
- In `tests/conftest.py`, retain both table fixtures and their specified key schemas.
- Make no cloud, network, build, deploy, lifecycle, dependency-installation, or unrelated test-fix changes.

## Implementation

1. Inspect and edit only the four authorized source files, removing their conflict markers while retaining the requested semantic union.
2. Confirm no conflict markers remain and run `bash -n be-validator-agent/trigger/build.sh`.
3. Parse both Python files with `ast.parse` using the existing offline Python interpreter, without importing modules or producing side effects.
4. From `be-validator-agent/trigger`, run `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=..:../../be-document-processing/src .venv/bin/python -m pytest tests -q -ra`; prepend `.venv/bin` to `PATH` if subprocess tests require Python discovery.
5. Record actual results, including any failures; preserve prior evidence and do not claim runtime or deployment success.

## Testing

- Shell syntax: `bash -n be-validator-agent/trigger/build.sh`.
- Conflict-marker scan across all four files.
- Side-effect-free `ast.parse` checks for `common.py` and `tests/conftest.py`.
- Offline suite from `be-validator-agent/trigger`: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=..:../../be-document-processing/src .venv/bin/python -m pytest tests -q -ra`.
- Verify case status/webhook, execution owner, enqueue, worker, backfill, DLQ, template, and worker-HTTP tests remain present and are executed; report the test runner's actual outcome.

## TDD: skip

This is a user-prescribed mechanical conflict resolution with existing tests; creating artificial RED evidence is explicitly disallowed.

## Files

- `be-validator-agent/trigger/build.sh` — preserve light/package copies of lifecycle and execution handlers, and audit module sync.
- `be-validator-agent/trigger/common.py` — preserve constructor initialization and add the specified cases, execution, and audit accessors.
- `be-validator-agent/trigger/template.yaml` — retain both complete sides of all three parameter/IAM conflict blocks.
- `be-validator-agent/trigger/tests/conftest.py` — retain both case and execution table fixtures.

## Progress

- [x] Create plan at the canonical task-specific path.
- [ ] Resolve exactly the four authorized conflict regions.
- [ ] Run prescribed offline verification and record results.
