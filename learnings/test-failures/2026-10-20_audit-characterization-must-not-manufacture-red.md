---
title: "Audit characterization must not manufacture RED"
date: 2026-10-20
category: test-failures
component: backend
tags: [tdd, audit, monitoring, proof]
file_type: rules
---

# Audit characterization must not manufacture RED

The expanded monitoring cache tests passed immediately, so the task-scoped TDD helper rejected RED; it then refused GREEN because no valid RED existed for this task. A genuine RED from the parent task was available, but it was preserved rather than copied or reconstructed as if it belonged to this task. Reuse the existing proof artifact only within its actual task lineage, and record the missing task-scoped proof as a blocker instead of manufacturing test evidence.

## Context
Extracted from task: [acceptance-fix] Monitoring cache reuse: dokončit požadovanou validační, izolační a fail-open test m
