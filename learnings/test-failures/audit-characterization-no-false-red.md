---
title: "Audit characterization must not manufacture RED"
date: 2026-10-20
category: test-failures
component: backend
tags: [tdd, audit, monitoring, proof]
file_type: rules
---

# Validating audit event matrices without falsifying TDD evidence

For test-only characterization tasks where the existing implementation already satisfies every new assertion, the proof-capture helper correctly rejects a passing RED and will not start GREEN without a task-scoped RED. Preserve the parent task's genuine failing output as provenance, then report the incompatibility honestly; do not introduce an intentionally wrong assertion or hand-write proof output. This project’s PageCacheReused behavior already passed the added validation, document isolation, payload allowlist, no-I/O construction, dispatch and FileReceived fail-open characterization matrix.
