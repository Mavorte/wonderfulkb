---
title: "Case Client: Globální Scan musí mít vlastní cursor a live důkaz"
date: 2026-10-19
category: architecture
component: backend
tags: [case-client, pagination, dynamodb, live-integration, tdd]
file_type: rules
---

# Planning global case listing when existing cursors are client-bound

The existing DynamoDB case-list implementation is not safely reusable with a missing `client_id`: its list path performs a client lookup and queries a per-client GSI. Global listing needs an explicit route/repository path using a bounded Scan on the cases table, plus its own cursor fingerprint and `case_id` resume key. Preserve continuation within an SDK page, and test the actual handler with Stubber to prove no client reads or per-client Query occur.

For authorized live verification, extend the existing component deploy and HTTP runner. Treat the approved contract as the source of exact resource, fixture, attempt, rollback, evidence, and credential limits; local test success does not establish the deployed hash or live behavior.

The task also exposed a proof-workflow hazard: a previous completed TDD proof under the same task ID may prevent a new RED capture. Check the canonical proof path before beginning implementation and do not replace historical evidence or treat an earlier GREEN as proof for new changes.
