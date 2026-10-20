---
title: "Plan conflict-resolution integrations around caller behavior"
date: 2026-10-20
category: architecture
component: backend
tags: [integration, conflict-resolution, queue-lifecycle, compatibility]
---

# Planning conflict-resolution integrations

For a conflict-resolution task that explicitly preserves independent local and upstream features, plan caller-level behavior checks alongside the file merge. Preserve protocol compatibility when result objects subclass `str`: attached metadata does not invalidate existing equality/hash/count behavior. In queue-driven lifecycle transitions, verify the state change is gated on a confirmed send and retain retry semantics for failed or ambiguous sends. The task constraints may explicitly prohibit repository operations or live integrations even when the project ordinarily deploys completed changes; honor the narrow task boundary.
