---
title: "Generation-aware claims preserve old-message semantics"
date: 2026-10-20
category: architecture
component: backend
tags: [wonderfulkb, monitoring, execution-identity, sqs, dynamodb]
file_type: decisions
---

# Generation-aware claims must preserve old-message semantics

In `be-validator-agent/trigger`, old document SQS messages (`v=1`) contain only case/document IDs, while the worker's business conditional claim depends on `queued` or an expired `processing` row. Once an execution-only run generation is introduced, an old delayed message could otherwise claim a later run simply because its business row is queued again.

Plan a conditional bootstrap for already queued/processing pre-upgrade rows and bind legacy messages exclusively to that legacy generation. New messages carry the owner-committed generation and run ID; after a terminal requeue a stale old-generation message is skipped. A claim transaction updates the unchanged business eligibility/lease fields *and* CAS-increments an execution-only attempt counter. On an ambiguous transaction response, read back the per-invocation claim token before deciding to retry; otherwise a successful claim can be counted twice. A new invocation after lease expiry is a legitimate new attempt even if SQS redelivers the same MessageId.

The narrow execution ledger remains the authority for run/attempt identity; the audit sink only records confirmed boundaries and cannot repair missing identity or prove whether an ambiguous SQS send was accepted.
