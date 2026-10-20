---
title: "Worker audit producers require real execution context"
date: 2026-10-20
category: architecture
component: backend
tags: [wonderfulkb, monitoring, audit, worker, tdd]
file_type: rules
---

# Worker audit producer planning

The current checked-in trigger still has a status-string claim, discards the SQS send response, and calls `run_document` without immutable attempt context. An audit contract document does not establish a callable producer boundary. Before implementation, inspect the actual owner-provided context and artifact composition; if they are absent, retain the boundary as unsupported instead of inventing identity or changing execution semantics. Base any supported mapping on actual callers and behavior tests; do not use Markdown searches as behavior proof.

The caller-side tests should compare NoOp, functioning, and failing sinks for unchanged business write order, return/errors, and provider-call counts. Verify the intended modern Python environment and declared dependencies before capturing a new RED proof; an old missing-dependency failure is not behavioral RED evidence.
