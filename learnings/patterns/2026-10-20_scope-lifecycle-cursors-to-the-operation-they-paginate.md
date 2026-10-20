---
title: "Scope lifecycle cursors to the operation they paginate"
date: 2026-10-20
category: patterns
component: backend
tags: [pagination, cursor, bounded-reads, monitoring]
file_type: rules
---

# Scope lifecycle cursors to the operation they paginate

The lifecycle implementation combined bounded audit reads, a reducer, and operation-bound cursors. Reuse this combination for lifecycle views: bound the underlying reads and scope pagination state to its operation rather than treating a cursor as interchangeable across operations.

## Context
Extracted from task: [acceptance-fix] Monitoring lifecycle HTTP: skutečné bounded routes a funkční end-to-end ověření: go
