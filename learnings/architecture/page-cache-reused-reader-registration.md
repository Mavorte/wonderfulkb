---
title: "PageCacheReused: explicit document reader registration"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, dynamodb, event-contract, cache]
---

# PageCacheReused audit persistence

Adding a new audit event to the DynamoDB writer is not sufficient for round-trip coverage. The document reader has a separate explicit event-type registry in `audit_queries.py`; register new event classes there as well, including the returned item type annotation.

For a cache reuse event, preserve cached result metadata under `cached_*` names. It describes the reused stored outcome, not execution performed by the current attempt. Store no page contents or cache location in the event allowlist.
