---
title: "Audit event allowlists and pytest runtime compatibility"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, events, pytest, python]
---

The audit model uses explicit event serialization allowlists and storage reads dispatch solely from the persisted `type`. Extending event types requires both additions: model `to_item`/`from_item` handling and query read dispatch. Focused pytest collection can fail before executing tests when the environment's Python is too old for existing `list[float] | None` model annotations; inspect this collection traceback before attributing RED to the new contract.
