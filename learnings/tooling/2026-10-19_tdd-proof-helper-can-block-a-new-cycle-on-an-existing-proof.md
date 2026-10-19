---
title: "TDD proof helper can block a new cycle on an existing proof"
date: 2026-10-19
category: tooling
component: tooling
tags: [tdd, proof-capture, workflow]
file_type: rules
---

# TDD proof helper can block a new cycle on an existing proof

When starting a new TDD cycle, the required proof helper rejected the task’s existing proof as “not a valid complete proof for this task.” The existing proof was left unchanged, and implementation and deployment did not proceed. Before retrying, resolve why the helper considers the current proof invalid; avoid editing production code or starting AWS operations until the required RED proof can be captured.

## Context
Extracted from task: Case Client: nasadit GET /cases a prokázat funkčnost přes HTTP
