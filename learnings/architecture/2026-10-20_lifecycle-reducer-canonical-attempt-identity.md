---
title: "Lifecycle reducer: canonical attempt identity and terminal reconciliation"
date: 2026-10-20
category: architecture
component: backend
tags: [wonderfulkb, monitoring, audit, lifecycle]
---

For WonderfulKB's bounded lifecycle reducer, use the terminal event's documented public scalar fields (`run_id`, `attempt_no`, and `outcome`) as its attempt identity and result only after checking the current serializer against the approved event contract. Do not invent aliases or fallback cascades. Reconcile a general terminal fact with a matching specific status as one consistent observation; reserve ambiguity for genuinely conflicting outcomes or unresolved scope. Terminal-only observations remain evidence, not proof of a missing start or a complete/latest execution history.
