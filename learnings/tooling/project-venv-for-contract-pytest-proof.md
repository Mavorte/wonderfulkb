---
title: "Použij projektový venv pro contract pytest proof"
date: 2026-10-20
category: tooling
component: backend
tags: [pytest, tdd, venv, openapi]
---

For focused pytest proof in `be-document-processing`, use the checked-in `.venv/bin/python -m pytest ...` rather than assuming `pytest` is on PATH or system Python has project test dependencies. The system interpreter's conftest import failed on missing `pymupdf`; the project virtualenv loaded the suite correctly and captured genuine RED evidence.
