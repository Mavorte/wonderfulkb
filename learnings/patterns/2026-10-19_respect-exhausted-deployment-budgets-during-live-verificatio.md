---
title: "Respect exhausted deployment budgets during live verification"
date: 2026-10-19
category: patterns
component: general
tags: [deployment, verification, task-budget]
file_type: rules
---

# Respect exhausted deployment budgets during live verification

The inherited task evidence stated that deployment attempts and the write budget were exhausted, and prohibited refreshing that budget. Live deployment and HTTP verification therefore remained incomplete; local tests and build results were reported separately, without implying live verification. Check inherited deployment constraints before attempting a live check, and record the remaining verification gap explicitly.

## Context
Extracted from task: [acceptance-fix] Case Client: GET /cases napříč všemi klienty: goal-001: Case Client: GET /cases nap
