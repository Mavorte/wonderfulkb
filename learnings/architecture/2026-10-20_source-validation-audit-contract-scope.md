---
title: "Audit source-validation events are a contract slice, not producer evidence"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, monitoring, source-validation, events]
file_type: rules
---

# Audit source-validation events are a contract slice, not producer evidence

Planning the source-validation audit slice exposed an important scope distinction: adding typed `StepStarted`/terminal event persistence with real `run_id` and `attempt_no` defines what the audit can accept, but does not establish that a checked-in or deployed worker emits those events. Keep execution identity producer-supplied, accept terminal-only history fragments, and never infer or synthesize missing starts. Use the existing conditional `event_id` persistence and explicit serialization allowlists; isolate fail-open behavior at the business-facing audit boundary while keeping direct validation strict. Hermetic Moto tests prove only event/store behavior, not live worker integration.
