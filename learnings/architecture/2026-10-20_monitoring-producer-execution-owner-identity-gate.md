---
title: "Monitoring producer requires execution-owner identity"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, execution-identity, queue, pytest]
file_type: decisions
---

# Producer integration requires execution-owner identity

The validator trigger currently discards the SQS `send_message` response, its conditional claim produces only a status string, and the worker invokes `run_document` without per-execution context. Existing row state and queue delivery do not provide a stable logical run identity or an atomic attempt ordinal. The build staging script also is not proof of canonical deployed image provenance.

For monitoring producers, do not substitute SQS receive count, UUID/hash/timestamp generation, or a test adapter for the execution owner's identity contract. First obtain approval for stable enqueue identity and confirmed/ambiguous send semantics, atomic claim-plus-attempt behavior including expired-lease/crash semantics, and immutable explicit context forwarding. Until then preserve the blocker and avoid changing execution semantics.

Verification note: use the designated project virtualenv and install the validator worker's declared `trigger/requirements-worker.txt` dependencies before interpreting missing imports as test failures. In this environment the interpreter existed but had no pip module and lacked `pypdf`; bootstrapping pip in that venv and installing the declared requirements allowed the unchanged focused pytest invocation to pass.
