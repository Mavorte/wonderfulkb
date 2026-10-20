---
title: "Planning the FileReceived read API safely"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, audit, authorization, deployment]
file_type: rules
---

# Planning a read API over the existing FileReceived audit store

The existing audit package already exposes a bounded `AuditStore.read_document` interface with document-partition queries and scope-bound continuation tokens. A monitoring route should map that interface into HTTP and must not recreate its reader or interpret read failure as an empty history.

For this task, the contract input and deployment instructions differ in ownership: the later task-specific instruction says to read and validate the shared OpenAPI YAML without changing it, even though older guide text describes narrowing it. Follow the explicit current ownership instruction and record any route/schema mismatch rather than silently editing the shared contract.

Intake currently authenticates a shared API key and checks case existence for uploads; neither proves the caller's per-case entitlement. Establish a real trusted authorization seam before exposing the read route. If none exists, retain the blocker explicitly and do not manufacture an auth fallback.

An API read addition is not complete on TestClient/build evidence alone: verify the package in the actual intake artifact, guarded in-place AWS test deployment, deployed revision/digest, and the route itself over authenticated HTTP using a bounded authorized synthetic fixture.
