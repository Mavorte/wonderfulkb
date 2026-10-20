---
title: "Monitoring OpenAPI: eventové DTO ověřovat sémanticky"
date: 2026-10-20
category: test-failures
component: backend
tags: [openapi, yaml, contract-tests, event-dto]
file_type: checklist
---

# Planning canonical audit lifecycle reducers

When planning an audit lifecycle reducer, inspect the actual event `to_item()` serializers before defining reducer semantics. Run and attempt terminal fields differ (`run_status` versus `attempt_status`), and optional attempt attribution on a run terminal must not manufacture an attempt observation.

Deduplication by event identity is safe only for equivalent payloads. Conflicting payloads sharing identity must remain visible as ambiguity, regardless of input order. Define focused tests for canonical status, conflict evidence, missing/contradictory scope, caller-supported availability, and explicit read failure before implementation; retain the bounded-window, partial-coverage, and opaque-cursor guarantees.

Keep source/test ownership narrow and preserve prior acceptance and proof artifacts when opening a distinct completion task.
# Monitoring OpenAPI: prove event semantics, not just YAML shape

For event-contract changes, parsing YAML and resolving `$ref`s only establish structural integrity. Derive a required-field/type/enum matrix from each event's canonical brief, then validate representative accepted and rejected payloads with available offline OpenAPI/JSON Schema validators.

Keep public DTO fields distinct from internal envelopes. Preserve intentional event-specific exceptions (for example, FileReceived without run scope and RunFinished with optional attempt scope); do not replace event-specific status fields with a generic outcome. A bounded source contract is not route/deployment evidence, and a shared API key does not prove case authorization.
