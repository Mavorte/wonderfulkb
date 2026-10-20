---
title: "PageCacheReused audit scope and evidence"
date: 2026-10-20
category: architecture
component: backend
tags: [wonderfulkb, monitoring, audit, cache-reuse, idempotency]
file_type: rules
---

# Planning note: narrow cache-reuse audit contract

For WonderfulKB monitoring, treat `PageCacheReused` as a content-free event/store contract for an explicitly supplied, successfully loaded and validated cached page. Its run/attempt identify the current use only. Persist the validated cached status (including `failed`) and only known cached metadata; never infer source execution identity or create a page/step terminal event as a side effect.

When planning this event-only slice, keep the boundary explicit: a pytest/Moto round-trip proves only the contract and persistence adapter. It does not prove the real worker's cache branch or a deployed producer. Existing event allowlists and conditional event-id persistence are the appropriate patterns to extend.
