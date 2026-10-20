---
title: "Bounded monitoring read plans preserve observation semantics"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, audit, cursors, authorization, deployment]
file_type: rules
---

# Monitoring read plans must separate observation views from lifecycle projections

When planning a monitor endpoint over the existing audit store, keep the HTTP adapter scoped to one bounded reader window and represent the result as partial observations. A cursor for a filtered view must bind the route operation and all path/query scope, and advance by the last evaluated position so an empty filtered page can still continue. Do not turn missing events into inferred lifecycle states or issue extra reads to fill the page.

For this repository, reuse the existing pure page-observation mapper only for its defined page event semantics; do not duplicate it for step events. Intake's shared API key and case existence check do not establish per-case authorization. The auth seam must be verified before exposing a case-scoped read.

Local tests and package builds are insufficient evidence for a read API deployment: record artifact/revision provenance and verify the changed route itself over bounded authenticated HTTP against an authorized synthetic fixture.
