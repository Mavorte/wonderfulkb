---
title: "Trigger audit identity requires execution-owner contract"
date: 2026-10-20
category: architecture
component: backend
tags: [wonderfulkb, trigger, audit, queue, attempt-identity]
---

# Authoritative execution identity is a producer prerequisite

For WonderfulKB trigger integration, audit listeners cannot manufacture run or attempt identities. The checked-in queue producer discards the SQS send response, while the worker's conditional claim changes only status/timestamp and has no atomic attempt ordinal or claim token. `ApproximateReceiveCount` is diagnostic only. Before emitting RunQueued/AttemptStarted or threading execution context, the canonical execution owner must specify confirmed-versus-ambiguous enqueue behavior and an atomic successful claim-plus-attempt result. If that contract is absent, record the blocker and stop rather than add speculative counters, an outbox, or a mock-only adapter.
