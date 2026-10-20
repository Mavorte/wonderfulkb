---
title: "PageCacheReused artifact round trips"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, dynamodb, serialization, tdd]
---

# PageCacheReused artifact round trips

Audit event `artifact_ids` is normalized to a tuple on construction, but DynamoDB serializes it as a list. `PageCacheReused.from_item` must convert that list back to a tuple so read values preserve event equality. An assertion comparing the event directly to the persisted read result detects this contract mismatch; when a test also checks the persisted first-write item, compare the normalized event and immutability separately.

The TDD proof helper writes beneath the selected evidence root. Run from the monorepo root or pass `--project-root` consistently so a required proof does not accidentally land under a component subdirectory.
