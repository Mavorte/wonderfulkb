---
title: "Continuation-scoped live budgets"
date: 2026-10-19
category: tooling
component: backend
tags: [case-client, live-deployment, budgets, tdd]
---

## Continuation-scoped live budgets

When extending an operational runner for a newly authorized continuation, bind the continuation ID to its own manifest path and explicit independent limits. A generic caller-provided limit is not a sufficient guard: the new continuation must cap forward deployment attempts separately from its reserved recovery attempt. Keep prior continuation tuples unchanged and reject unrecognized IDs. A first broad test that happens to pass cannot be accepted as RED; narrow the assertion to a guard that is demonstrably missing before production edits, then capture that exact focused command through proof-capture.

For partial completion, distinguish offline gates from actual live proof. Passing unit tests, compile, SAM validation, and application builds do not establish deployed Lambda/API configuration or live HTTP behavior.
