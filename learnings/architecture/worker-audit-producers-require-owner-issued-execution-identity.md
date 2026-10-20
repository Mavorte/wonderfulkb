---
title: "Worker audit producers require owner-issued execution identity"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, worker, execution-identity, fail-open]
---

# Worker audit producers require owner-issued execution identity

The checked-in trigger worker cannot safely emit attempt or run lifecycle events until its execution owner supplies authoritative identity and outcome interfaces.

`claim_document` currently returns a status string after a conditional row update; it does not atomically return a stable run ID and attempt ordinal. `Context.send` discards the SQS response, so the enqueue caller cannot distinguish confirmed acceptance from ambiguous delivery. `process_document` forwards only case/document IDs and warm-cached options. These are execution-contract gaps, not missing instrumentation helpers.

Do not synthesize attempt identity from receive count, timestamps, counters, or a warm-container global. Do not change claim/lease/retry or queue behavior to satisfy audit events. Record the seams as unsupported and require owner-approved canonical build provenance, confirmed enqueue outcomes, atomic claim+attempt identity, and explicit immutable context forwarding before producer integration.

For focused behavioral verification, use the declared project venv (`be-document-processing/.venv/bin/python`) from repository root. In this task it had Python 3.13, pytest 9.1.1, and pypdf 6.21.1; pipeline tests passed while the contract test correctly exposed the absent interface.
