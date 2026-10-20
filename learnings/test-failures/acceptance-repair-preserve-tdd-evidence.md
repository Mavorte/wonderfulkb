---
title: "Acceptance repair: preserve and validate TDD evidence"
date: 2026-10-20
category: test-failures
component: backend
tags: [acceptance, tdd, pytest, proof]
file_type: rules
---

# Planning an acceptance repair without mislabeling TDD evidence

When a prior acceptance run is reopened, inspect the preserved implementation diff, focused tests, parent plan, and proof artifacts before planning the repair. A pytest collection failure caused by a missing dependency is not behavioral RED; preserve it as historical evidence and require a fresh expected assertion failure only when the implementation is still absent. Keep the follow-up bounded to the unmet acceptance findings and retain already-completed tests.
