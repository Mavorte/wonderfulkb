---
title: "Require an implementation-specific failure for TDD RED proof"
date: 2026-10-19
category: test-failures
component: backend
tags: [pytest, tdd, dependency-setup]
file_type: rules
---

# Require an implementation-specific failure for TDD RED proof

The focused pytest run failed while loading `conftest.py` because `pymupdf` was missing. Installing `be-document-processing/requirements.txt` was also blocked because the configured package index did not contain pinned `fastapi==0.147.0`. The capture helper accepted this setup error as RED, but it did not establish the expected missing-audit-API failure. When capturing TDD proof, verify the failure reaches the target test and is caused by the behavior under change; resolve or explicitly record environment blockers before implementing production code.

## Context
Extracted from task: Monitoring MVP: uložit a přečíst jeden FileReceived event
