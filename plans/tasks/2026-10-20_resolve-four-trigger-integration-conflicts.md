---
title: "Resolve four trigger integration conflicts preserving both features"
type: implementation
---
# Resolve four trigger integration conflicts preserving both features

## Goal
Resolve exactly four currently marked content conflicts in the existing WonderfulKB checkout. Preserve upstream case lifecycle/webhook AND local monitoring execution/audit. This is a new explicit user request 2026-10-20 12:46, not continuation/reopening of cancelled task0a9eea03. The prior broad task is cancelled; do not revive its investigation. User supplied exact resolutions below. Do not broaden scope or redesign behavior.

## Scope
Only /Users/michal/Projects/wonderfulkb, edits ONLY:
- be-validator-agent/trigger/build.sh
- be-validator-agent/trigger/common.py
- be-validator-agent/trigger/template.yaml
- be-validator-agent/trigger/tests/conftest.py
Task-specific concise plan/evidence/learnings permitted. Other files and preexisting changes must remain unchanged. No cloud/network/provider, build/deploy execution, lifecycle commands, dependency reinstall, private data, sibling repos. Host owns version-control operations; worker only edits these four files and runs offline checks/tests. Existing conflicting files contain Updated upstream (remote) and Stashed changes (local) markers. Remove markers by preserving semantic union described below, never choose wholesale one side.

## Exact resolutions
### build.sh
Replace the entire conflict block with:
```bash
for f in __init__ common enqueue_handler dlq_handler processing_execution_context processing_execution_claims; do cp "$f.py" build/light/trigger/; done
for f in __init__ common enqueue_handler dlq_handler worker_handler case_step wonderful_webhook processing_execution_context processing_execution_claims; do cp "$f.py" build/pkg/trigger/; done
mkdir -p build/light/document_processing/audit build/pkg/document_processing/audit
cp ../../be-document-processing/src/document_processing/__init__.py build/light/document_processing/
cp ../../be-document-processing/src/document_processing/__init__.py build/pkg/document_processing/
rsync -a "${COMMON[@]}" ../../be-document-processing/src/document_processing/audit/ build/light/document_processing/audit/
rsync -a "${COMMON[@]}" ../../be-document-processing/src/document_processing/audit/ build/pkg/document_processing/audit/
```
### common.py
Preserve the preceding def __init__ line. Its continuation becomes (correct class indentation):
```python
                 dlq_url=None, ddb=None, sqs=None, s3=None, cases_table=None,
                 execution_table=None, audit=None):
```
Preserve ALL initializations including self.cases_name, self.execution_name and self.audit. For the second conflict include the immediately preceding @property and replace that entire region with these correctly indented members:
```python
    @property
    def cases(self):
        return self.ddb.Table(self.cases_name)

    def get_case(self, case_id):
        return self.cases.get_item(
            Key={"case_id": case_id}, ConsistentRead=True
        ).get("Item")

    @property
    def execution(self):
        return self.ddb.Table(self.execution_name)

    @property
    def audit_listener(self):
        if self.audit is None:
            from document_processing.audit.audit_listener import from_env
            self.audit = from_env()
        return self.audit
```
Do NOT add @property to get_case or duplicate decorators. No other common.py business logic changes. EnqueueResult and ClaimResult inherit str: comparisons to queued and claimed are compatible and must not be rewritten.
### template.yaml
Three conflict blocks: preserve BOTH sides' complete contents and YAML indentation, remove only markers/separators. Parameters CasesTable + WonderfulWebhookSecretName + AuditTable. Enqueue IAM CaseIntake + ExecutionLedger + AtomicQueue + AtomicWrite + AppendAudit. Worker IAM CaseEvaluating + WonderfulWebhookSecret + ExecutionLedger + AppendAudit. Identically named Sid in DIFFERENT IAM policy blocks is valid, do not remove them. Preserve ExecutionTable, EXECUTION_TABLE, AUDIT_TABLE_NAME, CASES_TABLE, WONDERFUL_WEBHOOK_SECRET and all unrelated resources/env outside conflict blocks.
### tests/conftest.py
Preserve BOTH table creation calls: wonderfulkb-uw-cases (case_id HASH) and wonderfulkb-trigger-execution (pk HASH/sk RANGE). Remove only conflict markers/separator.

## Verification
Do not execute build/deploy scripts. `bash -n be-validator-agent/trigger/build.sh`. Check the four files have no conflict markers and Python files compile using ast.parse without side effects.
Existing offline environment: be-validator-agent/trigger/.venv/bin/python. From trigger directory use `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=..:../../be-document-processing/src .venv/bin/python -m pytest tests -q -ra`; prepend .venv/bin to PATH if subprocess tests require python. Fixtures use moto fake credentials, no real AWS. In particular case status/webhook, execution owner, enqueue, worker, backfill, DLQ, template and worker-HTTP tests must remain present/executed. Report failures honestly; do not fix unrelated tests or modify more files to force green. No fake TDD evidence or artificial RED: this is user-prescribed mechanical conflict resolution; existing conflict syntax is not a behavioral RED. Preserve historical proofs.

## Acceptance
Exactly the semantic union above, four source-file edit scope, no conflict markers, offline suite results, shell syntax valid. No new behavior/refactor, no deletion of either feature. Concise final evidence identifies files and actual test results. No runtime/deployment success claim. Host separately finalizes repository integration after inspecting diff and tests.
