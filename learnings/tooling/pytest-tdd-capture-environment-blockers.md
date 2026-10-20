---
title: "pytest TDD capture: environment blockers"
date: 2026-10-20
category: tooling
component: backend
tags: [pytest, tdd, dependencies, proof-capture]
---

## Focused pytest capture in this repository

The shell environment may not expose a `pytest` executable, so use the explicit `python3 -m pytest ...` command with the TDD proof-capture helper; the helper validates command identity between RED and GREEN. A first RED can be blocked before test collection by missing declared dependencies (`pymupdf`). The repository requirements currently pin `fastapi==0.147.0`, which the configured package index did not offer, so dependency installation failed before tests could reach the intended import failure. Resolve test-environment dependencies before treating an infrastructure failure as a genuine RED; only accepted RED proof is permission to edit production code.
