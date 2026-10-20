---
title: "Lifecycle acceptance repair: DTO drift and functional proof"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, lifecycle, acceptance, tdd, openapi]
file_type: rules
---

# Lifecycle acceptance repair: DTO drift and functional proof

When reopening the lifecycle HTTP acceptance task, inspect both the parent GREEN assertion and the current OpenAPI schema against the reducer output. In this repository the parent GREEN asserted only unconditional 403; it cannot stand in for authorized bounded HTTP output. The YAML run/audit DTOs advertise `lifecycle`, `terminal`, and `publication`, while `audit_lifecycle_observations` returns `state`, `terminal_state`, `published_results`, availability and full evidence. Plan a narrow DTO reconciliation alongside the adapter, and start the follow-up test with an authorized-provider fake whose first assertion fails on 403 vs 200; preserve the parent's genuine registration RED unchanged. Verify the producer-owned `ResultPublished` event and audit decoder before promising publication observations: the YAML lists it, but the shared reader currently cannot decode it.
