---
title: "Bounded audit lifecycle summaries preserve uncertainty"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, monitoring, lifecycle, tdd]
---

# Bounded audit lifecycle reducer

Lifecycle summaries must describe only the supplied audit window. Keep the caller's continuation token opaque, report partial coverage, and retain evidence per explicit run/attempt/publication identity. Missing start or queue events do not justify synthetic attempts; event absence is unknown, while conflicting terminals stay ambiguous rather than choosing the newest timestamp or sequence as business truth.

For TDD in this repository, verify the `be-document-processing/.venv/bin/python` interpreter and pytest import first, then capture the exact focused pytest command with the loaded proof helper. Broader package pytest may fail during collection because unrelated unfinished page-observation tests import absent modules or event classes; distinguish those collection failures from the focused test result.
