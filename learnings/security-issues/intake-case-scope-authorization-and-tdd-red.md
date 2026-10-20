---
title: "Intake case-scope authorization and truthful TDD RED"
date: 2026-10-20
category: security-issues
component: backend
tags: [fastapi, authorization, tdd, monitoring]
file_type: rules
---

In WonderfulKB intake, `x-api-key` authentication plus `require_case()` existence lookup is not a trusted per-case authorization boundary. A new case-scoped read route must not infer caller permission from either. Stop before route exposure and document the exact missing interface; deployment authorization does not waive application authorization.

For task-specific TDD proof, use the skill helper with the exact focused command. A helper may report an accepted execution attempt even when pytest fails collection; inspect `proof_outcome` and captured output to distinguish a genuine expected RED from an environmental failure such as missing FastAPI. Never proceed to production edits on the latter.
