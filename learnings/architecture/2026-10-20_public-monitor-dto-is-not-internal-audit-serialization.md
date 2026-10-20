---
title: "Veřejné monitoring DTO není interní auditní serializace"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, openapi, audit, dto, authorization]
file_type: rules
---

# Public monitoring DTO needs its own explicit projection

In be-intake, AuditStore decodes trusted event classes whose to_item() allowlists are storage contracts, not the public HTTP contract. Returning to_item() minus schema_version was insufficient: StepFailed retained duration_ms and internal error enums, PageCacheReused exposed artifact_ids absent from its public schema, and page/terminal/retry diagnostics differed from the sole YAML.

Validate real authenticated HTTP responses for every supported event type against be-document-processing/contracts/openapi-processing-monitor.yaml. Stub only provider I/O and execute the real grant/membership adapter and AuditStore. Keep explicit per-type public field allowlists in processing_monitor_routes.py; do not broaden the YAML or storage model merely to make serialization pass. Required internal failure details can be mapped to the approved coarse PROCESSING_FAILED code; unsupported optional retry reasons must not invent a retry-exhausted conclusion.

Page fixtures with model metadata require an observed vision method; native plus model is invalid stored data and correctly becomes a read503. Correct fixture mistakes without disguising genuine schema failures. FileReceived-only GREEN does not prove other event DTOs.

Task task-cf441015-6bba-4862-8200-b2c0047f6905 captured a genuine second RED and52-pass GREEN over all13 event types. This is hermetic HTTP evidence, not AWS deployment or producer-live proof.