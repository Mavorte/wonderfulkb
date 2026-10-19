---
title: "Canonical plan header při obnově plánování"
date: 2026-10-19
category: tooling
component: tooling
tags: [compound-plan, planning, artifact-validation]
file_type: rules
---

# Canonical plan header must match the plan artifact parser

A dedicated plan can contain all required English `##` sections and still fail with `plan_artifact_invalid: status=invalid_header` when its first line is only `# Case Client — ...`. Start canonical task plans with `# Plan YYYY-MM-DD: ...`; check the actual file returned by `plan-path.py --touch` before finishing. Avoid skill-template status markers and headings when the caller restricts accepted section headings.

The path returned by `plan-path.py` is authoritative even during recovery: fix the existing file in place rather than creating a new plan or editing `plans/tasks/`.
