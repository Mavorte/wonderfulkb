---
title: "Case Client: server-generated UUID and bounded collision recovery"
date: 2026-10-19
category: architecture
component: backend
tags: [case-client, uuid, dynamodb, stubber, gitignore]
file_type: rules
---

# Server-generated case UUIDs with conditional DynamoDB inserts

For create-only APIs, caller-provided IDs should not silently reintroduce replay semantics. Ignore `case_id` in the POST payload and keep the repository create contract limited to the validated owner and metadata; each adapter generates a fresh UUIDv4 and the HTTP layer consistently returns `201`.

In DynamoDB, validate and strongly read the active client first, then atomically combine a client `ConditionCheck` with a case `Put` guarded by `attribute_not_exists(case_id)`. Classify transaction cancellation by the exact ordered reason codes. A case-key conditional failure is only a collision candidate: strong-read that generated key, discard it if occupied, and try another fresh ID within a small bound. Never return the occupant or treat the request as an idempotent replay. If the key is unexpectedly absent, reason codes are ambiguous, or attempts are exhausted, fail closed with a sanitized server error.

Stubber tests should pin the generated IDs and assert each complete SDK sequence, including `ConsistentRead=true`, condition position, collision recovery/exhaustion, and no pending responses. Preserve the public projection and Decimal metadata behavior during the API-contract migration.

For repository ignore-policy checks, test the root `.gitignore` in an isolated temporary Git repository with global/system excludes disabled. Use `git check-ignore -q` per candidate (rather than parsing `-v` output, which also prints negated rules) and include symlinked `node_modules` plus negative source/evidence paths.
