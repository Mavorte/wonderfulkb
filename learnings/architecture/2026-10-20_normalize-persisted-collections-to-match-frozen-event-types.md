---
title: "Normalize persisted collections to match frozen-event types"
date: 2026-10-20
category: architecture
component: backend
tags: [dynamodb, serialization, round-trip, events]
file_type: rules
---

# Normalize persisted collections to match frozen-event types

DynamoDB returned `artifact_ids` as a list, while the frozen event’s public value was a tuple, so round-trip equality failed. `PageCacheReused.from_item` now converts the persisted list back to a tuple. When adding persistence round-trip tests, check both values and types for collection fields, and normalize storage representations at the deserialization boundary.

## Context
Extracted from task: Monitoring cache reuse: dokončit požadovanou validační, izolační a fail-open test matici
