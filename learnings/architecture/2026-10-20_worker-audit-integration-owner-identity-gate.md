---
title: "Worker audit integration requires owner-issued identity"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, audit, worker, execution-identity, tdd]
file_type: rules
---

# Worker audit integration requires owner-issued identity

Before instrumenting the validator worker, verify that enqueue exposes a stable logical run identity and typed send outcome, claim atomically assigns a run ID and attempt ordinal, and that immutable context is forwarded through the canonical caller. In the current checkout, enqueue discards SQS response and claim returns only a status; the worker's warm-cached Options has no per-execution context. A signature-only change would not prove producer behavior and would invent unsupported identity. Preserve the parent task's genuine RED as historical evidence and wait for the execution-owner contract rather than fabricate a fresh proof or claim GREEN.
