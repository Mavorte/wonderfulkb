---
title: "Worker audit producers need an owner-issued execution identity"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, worker, execution-identity, producer]
file_type: rules
---

# Worker audit producers need an owner-issued execution identity

The worker could not safely emit audit producer events because `claim_document` returns only a status string, enqueue discards the SQS response, and `process_document` receives no authoritative execution context. Adding producers without that interface would require inventing execution identity or changing execution semantics. Reuse this check before instrumenting worker-side audit events: trace how the execution owner creates and passes identity through claim, enqueue, and processing; add producer calls only once that context is available. A focused test asserting the expected execution-context parameter made the missing interface explicit, but correctly remained RED until the owner-side contract exists.

## Context
Extracted from task: Monitoring worker: dokončit skutečná producer volání a behaviorální důkaz
