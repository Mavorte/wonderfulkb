---
title: "AttemptStarted audit contract preserves producer identity"
date: 2026-10-20
category: architecture
component: backend
tags: [wonderfulkb, monitoring, audit, attempt-identity]
---

For WonderfulKB audit-event planning, distinguish event/store acceptance from producer readiness. AttemptStarted may persist only producer-supplied stable event_id, run_id, and positive attempt_no; the known live worker does not currently establish run identity or increment a claim-attempt counter. Do not infer attempt_no from SQS receive count, audit row count, or mutable analysis timestamps, and do not describe a contract test as live-worker evidence. Preserve the existing document Query and conditional event_id idempotency while extending type-aware decoding.
