---
title: "A cursor length limit does not bound JSON nesting depth"
date: 2026-10-19
category: runtime-errors
component: backend
tags: [pagination, json, validation, offline-tests]
file_type: rules
---

# A cursor length limit does not bound JSON nesting depth

The Case & Client pagination cursor enforced a 4096-character limit, strict base64url decoding, and an exact versioned schema. Nevertheless, a payload containing 1100 nested arrays fit within the limit and caused `json.loads` to raise `RecursionError`. Catching only `ValueError` and `TypeError` let this invalid input become a sanitized HTTP 500 instead of HTTP 400.

Catch `RecursionError` at the cursor-decoding boundary and translate it to `InvalidRequest`, while preserving HTTP 500 handling for repository operational failures. A regression test through the real handler and adapter demonstrated the original `500 != 400` failure and passed after the fix. When testing encoded tokens, include small but deeply nested JSON in addition to oversized payloads and malformed base64.

## Context
Extracted from task: Case & Client: jedna Lambda s explicitními mock daty, offline testy a minimálním SAM balením
