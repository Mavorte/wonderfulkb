---
title: "Audit lifecycle reducer: preserve canonical status and conflicting evidence"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, lifecycle, observations, reducer]
---

# Lifecycle reducer observations

The audit serializer is the source of truth for lifecycle field names: `AttemptFinished` supplies `run_id`, `attempt_no`, and `attempt_status`; `RunFinished` supplies `run_id`, `run_status`, and optional `attempt_no`. That optional run-terminal number must not be treated as an attempt observation.

For bounded audit windows, deduplicate only exact payload duplicates with the same `(event_id, sequence)`. A collision with changed content must remain represented and force ambiguity, independent of input order. Availability declarations also need caller-provided evidence; empty observations alone mean unknown. Keep reducer read errors explicit rather than returning empty success.
