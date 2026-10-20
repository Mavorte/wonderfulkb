---
title: "Validator monitoring producer requires authoritative execution identity"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, validator-agent, execution-identity, audit]
---

# Runtime producer integration needs execution-owner identity semantics

The checked-in validator trigger stages source with `trigger/build.sh`, but that alone does not establish the provenance of a canonical deployed image. The enqueue path discards the SQS response, and the conditional claim only changes the document status; neither supplies durable logical run identity or atomic attempt numbering. A cached pipeline `Options` object is therefore not an appropriate carrier for per-run identity.

For audit producer work, stop at the source seam when those execution semantics are absent. Record the smallest owner contract (confirmed/ambiguous enqueue result and stable event/run identity; atomic successful claim plus attempt ordinal and crash/lease decisions; immutable argument propagation) rather than inventing a counter, outbox, or no-op adapter. Keep source tests and build provenance distinct from deployed proof.

For scoped Python verification, invoking the trigger suite from repo root exposed an import-path collection issue in `tests/test_backfill.py`; focused enqueue/worker tests worked. Record collection failures separately from focused test outcomes and unrelated package failures.
