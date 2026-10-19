---
title: "Case Client: pokračovací ledger a live guard"
date: 2026-10-19
category: tooling
component: backend
tags: [case-client, aws, deployment, ledger]
---

# Case Client continuation guard handoff

The deployment helper contains a continuation allowlist and fresh ledger path, but its task ID and private rollback pointer are task-scoped too. Starting a continuation requires updating that identity so private state cannot collide with an earlier task. The counter manifest itself must still be inspected and preserved; changing constants does not authorize resetting counters.

The existing HTTP runner does not automatically account every HTTP request in the deployment ledger, and API Gateway preflight only reads currently configured methods. A required new method therefore needs explicit additive create/deploy/readback and rollback ownership handling before any live deployment is safe. An offline passing unit suite is not evidence of the live route or end-to-end HTTP acceptance.
