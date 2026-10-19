---
title: "Case Client: oddělit source kontrakt od nasazeného stavu"
date: 2026-10-19
category: architecture
component: backend
tags: [case-client, dynamodb, api-contract, planning]
file_type: rules
---

# Case Client planning: distinguish a source contract from deployed state

When reconciling a newer API contract with an older deployed endpoint, preserve the boundary explicitly: source OpenAPI and implementation can specify server-generated UUIDv4 IDs while a dated quick-connect note reports that the deployed POST still requires caller IDs. The deployment note is evidence only about that deployment at its stated date, not about current source behavior or successful rollout.

For a server-generated key backed by DynamoDB, retain a conditional insert and strong read-back on a generated-key collision. Never return the collision occupant as a replay result or overwrite it. Bound retries with fresh generated IDs and turn exhausted collisions into a sanitized server error; test the exact transaction, cancellation reasons, and subsequent reads with botocore Stubber, not a live database.

When integrating read-only remote snapshots, use their manifest and source commit to establish scope and provenance, selectively reconcile files into current source, and leave the snapshots untouched. Keep unrelated schema/detail ambiguities recorded separately rather than expanding the feature silently.
