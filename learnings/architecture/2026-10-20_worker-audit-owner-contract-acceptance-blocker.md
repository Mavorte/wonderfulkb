---
title: "Worker audit hooks require an owner-issued execution contract"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, audit, worker, tdd, execution-identity]
file_type: rules
---

# Worker audit hooks require an owner-issued execution contract

The monitoring worker must not emit producer events by inventing run identities or attempt ordinals. Before instrumenting enqueue or claim callers, the execution owner must provide stable logical enqueue identity and typed send outcomes, an atomic claim-plus-attempt result, immutable per-execution context forwarding, and canonical build provenance.

When these are absent, follow the implementation plan's explicit blocker path: preserve existing execution semantics and unrelated working-tree changes, do not fabricate a failing RED merely to satisfy a proof checklist, and do not report GREEN or implementation completion. Resume behavior tests and integration only after the approved interface exists.
