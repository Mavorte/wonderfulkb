---
title: "Worker audit integration needs producer-owned identity"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, worker, execution-context, tdd]
---

# Audit worker integration requires producer-owned identity

When connecting lifecycle audit events to the validator worker, do not infer run or attempt identity from document keys, SQS receive count, warm-container state, or audit history. The checked-in queue helper discards the SQS response, the claim returns only a status string, and `process_document` calls `run_document` with mutable warm-cached `Options` but no per-execution context.

This means page/extraction/signature/publish observations cannot be supported by merely adding a listener to the pipeline. First the execution owner must define canonical build provenance, a stable enqueue identity/outcome, atomic claim plus attempt ordinal, and explicit immutable context forwarding. Until then, document each actual seam as unsupported and leave business execution unchanged. A test run that fails during import because a declared dependency is missing is not an implementation-level RED, even if a capture utility labels any nonzero exit as accepted RED; inspect captured output before interpreting the proof.
