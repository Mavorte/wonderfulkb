---
title: "Lifecycle reducer distinguishes retry attempts from identity conflicts"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, lifecycle, attempt-identity, evidence]
---

# Lifecycle attempt identity: separate retries from identity conflicts

Two AttemptFinished observations with distinct event identities and canonical attempt numbers in one run are legitimate separate attempts; neither differing attempt number nor same-run grouping proves ambiguity. Only reuse of the same event identity `(event_id, sequence)` with conflicting payload indicates an identity conflict, even when the conflicting payload changes run/attempt scope. Check this globally and retain both evidence entries independent of input ordering.

Canonical AttemptFinished scope is `run_id` + `attempt_no`, with `attempt_status`. A missing run scope must remain explicitly represented as unscoped uncertainty rather than disappearing as an empty observation or receiving an invented run ID. Contradictory supplied canonical/legacy ordinals must not select a certain attempt through a fallback.
