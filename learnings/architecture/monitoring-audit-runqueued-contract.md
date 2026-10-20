---
title: "Monitoring audit: RunQueued event identity and bounded decoding"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, audit, runqueued, dynamodb, pytest]
---

# RunQueued audit event contract

The existing audit log can retain a new event type without changing its storage key or document-query contract: serialize only explicit approved event fields and dispatch decoding by the stored `type` within the same bounded document Query.

`RunQueued` must receive a stable, nonempty opaque `run_id` from its caller. The event/store layer must not invent identity from document IDs, timestamps, random UUIDs, or queue delivery metadata. Optional context should be filtered at serialization to explicit allowlisted keys and nonempty string values; omitted context stays unknown. Keep FileReceived decoding on the same event path for backward compatibility.

Test setup gotcha: this package's `tests/conftest.py` imports the broader application during test collection. The system Python 3.9 cannot collect it because project models use newer typing syntax, and base collection dependencies such as PyMuPDF/FastAPI may be absent. Use the existing package `.venv` (Python 3.13 here) to capture the focused test. The project-wide suite may also reveal unrelated collection errors when already-referenced observation modules are absent from source.
