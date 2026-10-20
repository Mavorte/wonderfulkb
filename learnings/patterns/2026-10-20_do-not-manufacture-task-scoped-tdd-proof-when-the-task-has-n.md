---
title: "Do not manufacture task-scoped TDD proof when the task has no RED phase"
date: 2026-10-20
category: patterns
component: tooling
tags: [tdd, proof, task-checkpoint]
file_type: rules
---

# Do not manufacture task-scoped TDD proof when the task has no RED phase

The TDD helper rejected GREEN because this task had no task-scoped RED phase. The parent task’s genuine RED proof was preserved, but it could not substitute for the required proof here. Reuse the helper’s gate: keep parent evidence intact, record the checkpoint blocker, and do not fabricate a RED phase or claim behavioral completion.

## Context
Extracted from task: [acceptance-fix] Monitoring worker: dokončit skutečná producer volání a behaviorální důkaz: goal-001
