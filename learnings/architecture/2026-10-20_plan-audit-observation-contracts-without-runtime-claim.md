---
title: "Planning audit observation contracts without claiming runtime execution"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, monitoring, step-events, planning]
file_type: rules
---

# Planning audit observation contracts without claiming runtime execution

When planning an audit event/store slice, distinguish the event contract's accepted facts from producer semantics and live worker evidence. For a detector observation, preserve producer-supplied `event_id`, `run_id`, positive attempt, and time; store only a terminal status the producer actually returned or a captured failure. Disabled and unknown outcomes must not be converted into audit successes, and a contract/store-only slice must not add detector hooks or claim that a detector ran.

For existing Step events, check both the stage allowlist and `AuditStore` dispatch/type contract. The focused persistence test should assert `put == "inserted"` and then verify the decoded event and duration after a fake/Moto read; fail-open serialization can otherwise hide errors as `unavailable`. Plan terminal-only reads and invalid sensitive payload rejection explicitly, so missing earlier events remain uncertainty rather than synthesized history.
