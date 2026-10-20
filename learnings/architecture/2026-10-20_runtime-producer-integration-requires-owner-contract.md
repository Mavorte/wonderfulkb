---
title: "Runtime producer integration requires an execution-owner contract"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, execution-identity, trigger, tdd]
file_type: decisions
---

# Producer integration requires an authoritative execution-owner contract

The trigger's existing SQS and DynamoDB paths are insufficient to emit reliable run/attempt audit events. `Context.send` drops the SQS response, `claim_document` only returns a status string, and the worker passes a warm-cached `Options` object without immutable per-execution identity. The staging `build.sh` is not proof of the canonical deployed image/build.

When these interfaces are absent, stop before adding producer integration, generated identities, counters, or a permissive test double. An integration-shaped test that only proves a fake interface does not satisfy caller evidence. Keep the blocker explicit and require the execution owner to approve stable logical enqueue identity/outcomes, atomic claim-plus-attempt semantics including crash/lease behavior, and direct immutable context forwarding. Run independent existing tests, but do not manufacture RED/GREEN proof for a feature that cannot safely be implemented.
