---
title: "In-memory Lambda mocks provide only execution-environment-local idempotence"
date: 2026-10-19
category: architecture
component: backend
tags: [lambda, mock-repository, idempotence, state]
file_type: rules
---

# In-memory Lambda mocks provide only execution-environment-local idempotence

The mock repository supported create/repeat/conflict behavior, but its persistence and idempotence applied only within one repository instance or Lambda execution environment. A cold start restored fixtures, and separate Lambda instances maintained independent state.

Make this boundary explicit in mock API documentation and tests. Verify both repeated requests against the same repository and reset behavior with a new repository. Do not interpret successful local idempotence tests as evidence of durable or cross-instance idempotence.

## Context
Extracted from task: Case & Client: jedna Lambda s explicitními mock daty, offline testy a minimálním SAM balením
