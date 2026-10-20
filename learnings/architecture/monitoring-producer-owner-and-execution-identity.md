---
title: "Monitoring producer: verify owner and execution identity first"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, execution-context, audit, source-provenance]
file_type: rules
---

Monitoring producer work must separate what source equivalence proves from what runtime identity requires. Module-level byte equivalence for enqueue/worker code does not establish the complete canonical build caller. Before wiring audit events, verify both the actual caller ownership and an approved execution contract for confirmed versus ambiguous enqueue, atomic claim plus attempt numbering, and immutable context forwarding. If those guarantees are missing, report the smallest execution-owner decision as a blocker; do not invent runtime tables, counters, outboxes, identities, or mock-only producer proof. Keep audit event creation, serialization, I/O, and fail-open isolation inside the audit package behind one injected listener.
