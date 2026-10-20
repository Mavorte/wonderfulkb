---
title: "Focused pytest capture environment blockers"
date: 2026-10-20
category: test-failures
component: backend
tags: [pytest, tdd, dependencies, proof-capture]
---

# Focused pytest captures and environment failures

For `be-document-processing`, the repository test `conftest.py` imports PyMuPDF before any test module runs. A focused test can therefore fail at collection with a missing dependency, which is not a valid implementation RED. Inspect the captured stderr and require the expected missing-API assertion before production edits.

This environment also has a configured package index that did not provide the pinned `fastapi==0.147.0`; installation of the whole requirements file failed. Record the exact blocker and keep the failed capture as history rather than rewriting its evidence.

When the `pytest` executable is not on PATH, `python3 -m pytest` can be used, but keep that exact argv identical for RED and GREEN proof capture.
