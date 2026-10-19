---
title: "Validate execution prerequisites before starting a gated TDD workflow"
date: 2026-10-19
category: tooling
component: tooling
tags: [preflight, git, tdd, handoff]
file_type: rules
---

# Validate execution prerequisites before starting a gated TDD workflow

The deployment plan required a host-prepared feature branch while prohibiting the implementation agent from performing Git operations. The workspace was on `main`, so the agent could not satisfy the prerequisite itself and implementation was blocked.

For constrained execution plans, check both prerequisites and permission boundaries before editing sources or starting TDD. If a prerequisite requires an action outside the agent's authority, preserve a checkpoint with the exact blocker and request the necessary host preparation.

## Context
Extracted from task: Case & Client: nasadit náš Python na existující testovací API a odladit živou DB integraci
