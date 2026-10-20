---
title: "Keep extraction audit contracts observation-only"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, audit, extraction, event-contract]
file_type: rules
---

# Keep extraction audit contracts observation-only

When planning an extraction audit slice, separate the event/store contract from instrumentation. Require explicit producer-supplied `run_id`, `attempt_no`, event identity, and observed outcomes; the audit layer must not invoke an extractor or infer execution from business status. Empty completed-page input means no step event, while a successful extraction returning empty fields is still a successful return. Persist only the typed technical allowlist and preserve fail-open behavior at the business-facing audit boundary.

Hermetic fake/Moto roundtrips verify event serialization and persistence semantics only; they do not establish that a real worker ran extraction or that a deployed environment emits these events.
