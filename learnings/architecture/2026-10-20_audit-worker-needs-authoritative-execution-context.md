---
title: "Audit instrumentation requires actual execution context"
date: 2026-10-20
category: architecture
component: backend
tags: [wonderfulkb, monitoring, audit, attempt-identity, worker]
file_type: rules
---

# Audit instrumentation requires actual execution context

The checked-in validator pipeline already accepts explicit `Options`, but that does not itself provide reliable per-execution identity. The recorded trigger seam only returns a status from claim and does not supply a stable `run_id`/`attempt_no`; never infer these from SQS receive count, audit rows, or mutable timestamps.

Before wiring worker audit events, verify the canonical caller, build inclusion, and immutable context propagation from successful claim into the pipeline. If any prerequisite is absent, document the exact unsupported capability and blocker rather than inventing identity, adding a parallel execution model, or emitting synthetic success. Keep event creation, serialization, sink I/O, and fail-open isolation in the audit package behind one injected listener.
