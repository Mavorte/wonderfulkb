---
title: "Keep protected-route tests aligned with route additions"
date: 2026-10-19
category: test-failures
component: backend
tags: [case-client, sam, route-tests]
file_type: rules
---

# Keep protected-route tests aligned with route additions

After adding a protected REST route, the Case Client suite failed because a template test still expected four function events; the template now correctly contained five. Update route-count assertions when adding a route, then rerun the full relevant suite. The initial mismatch was stale test coverage, not a template defect.

## Context
Extracted from task: [acceptance-fix] Case Client: GET /cases napříč všemi klienty: goal-001: Case Client: GET /cases nap
