---
title: "Audit AttemptStarted: explicit identity and query ordering"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, attemptstarted, dynamodb, idempotency]
---

# Audit AttemptStarted contract

`AttemptStarted` is an explicit audit event, not an attempt allocator. Require the producer's nonempty `run_id`, stable `event_id`, and strict positive integer `attempt_no` (`bool` must be rejected despite Python's bool/int relationship). Serialize only these approved fields in addition to the common envelope.

Extend document-query decoding by event `type` while preserving the existing document partition query and conditional put idempotency. Query ordering is by event key (`event_id`), not by event `sequence`; test fixtures must arrange event IDs accordingly when asserting list order.
