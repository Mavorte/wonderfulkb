---
title: "RunQueued store contract stays separate from the producer"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, monitoring, run-identity, idempotency]
file_type: rules
---

# RunQueued store contract stays separate from the producer

When planning an audit-store addition for RunQueued, keep the store contract narrowly scoped: require the caller's real opaque `run_id`, whitelist only approved nonempty stored context, and preserve FileReceived's no-run envelope. Do not add identity generation or infer identity from document, timestamp, or queue receive count. A contract/store test using Moto establishes local serialization, idempotency, and read compatibility only; it does not prove a live producer or enqueue integration.

The existing event reader decodes a single bounded document Query. Adding an event type therefore requires type-aware item decoding while retaining the same query scope and continuation behavior. Keep `event_id` as the conditional idempotency key and `occurred_at` as the sole timestamp.
