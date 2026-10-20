---
title: "Audit lifecycle reducer planning: canonical status and conflicting evidence"
date: 2026-10-20
category: architecture
component: backend
tags: [wonderfulkb, monitoring, audit, reducer]
file_type: rules
---

# Planning canonical audit lifecycle reducers

When planning an audit lifecycle reducer, inspect the actual event `to_item()` serializers before defining reducer semantics. Run and attempt terminal fields differ (`run_status` versus `attempt_status`), and optional attempt attribution on a run terminal must not manufacture an attempt observation.

Deduplication by event identity is safe only for equivalent payloads. Conflicting payloads sharing identity must remain visible as ambiguity, regardless of input order. Define focused tests for canonical status, conflict evidence, missing/contradictory scope, caller-supported availability, and explicit read failure before implementation; retain the bounded-window, partial-coverage, and opaque-cursor guarantees.

Keep source/test ownership narrow and preserve prior acceptance and proof artifacts when opening a distinct completion task.
