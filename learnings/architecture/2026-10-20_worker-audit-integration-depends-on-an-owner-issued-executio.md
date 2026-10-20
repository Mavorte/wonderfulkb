---
title: "Worker audit integration depends on an owner-issued execution identity"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, audit, worker, execution-identity, tdd]
file_type: rules
---

# Worker audit integration depends on an owner-issued execution identity

The monitoring worker integration was blocked because the enqueue path had no stable run identity or typed send outcome, the claim path assigned neither a run ID nor an attempt ordinal, and canonical deployed build provenance was not established. Adding producer calls or forwarding context before those contracts exist would invent execution semantics. Reuse this gate: establish the execution-owner contract and deployed provenance before wiring audit producers; preserve the blocker rather than fabricating identity or claiming behavioral completion.

## Context
Extracted from task: [acceptance-fix] Monitoring worker: dokončit skutečná producer volání a behaviorální důkaz: goal-001
