---
title: "Keep FileReceived audit persistence within the MVP boundary"
date: 2026-10-19
category: architecture
component: backend
tags: [monitoring, audit, dynamodb, scope]
file_type: rules
---

# Planning a narrowly scoped FileReceived audit store

For the first monitoring persistence slice, use `plans/monitoring/mvp-reference-20261019.md` as the scope authority. Keep the package limited to the seven-field FileReceived envelope, a separate audit table with conditional stable-identity writes, and a document-partition bounded Query. Do not infer permission for producer hooks, HTTP, deployment, run projections, TTL, or fencing.

Tests should explicitly prove duplicate immutability, document separation, page continuation, Query rather than Scan, and propagation of read failures. A successful mock-state round trip is useful adapter evidence, but must not be described as verification of deployed persistence.
