---
title: "Generate case UUIDs on the server with bounded collision retries"
date: 2026-10-19
category: architecture
component: backend
tags: [case-client, uuid, dynamodb, conditional-write]
file_type: rules
---

# Generate case UUIDs on the server with bounded collision retries

Case creation now generates its UUID on the server; caller-supplied IDs are ignored, and successful creates return `201`. The DynamoDB adapter uses a conditional insert and bounded retries when an ID collides. Reuse this approach to avoid overwriting existing records while keeping collision recovery finite, and keep the handler, repository protocol, mock, event fixtures, and docs aligned on the same contract.

## Context
Extracted from task: Case Client: dokončit server UUID a odstranit projektové znečištění acceptance diffu
