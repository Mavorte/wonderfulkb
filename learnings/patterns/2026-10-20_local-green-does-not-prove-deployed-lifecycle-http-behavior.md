---
title: "Local GREEN does not prove deployed lifecycle HTTP behavior"
date: 2026-10-20
category: patterns
component: e2e
tags: [verification, deployment, evidence, aws]
file_type: rules
---

# Local GREEN does not prove deployed lifecycle HTTP behavior

Focused tests, audit and contract tests, backoffice tests, a build, and a Docker import smoke check passed, but deployment and direct HTTP verification did not occur. The remaining blockers were a missing trusted authorization provider and AWS CLI `NoCredentials`. Keep local correctness evidence separate from deployed end-to-end evidence; record unexecuted checks and blockers explicitly, and leave the acceptance checkpoint open until the actual target is exercised.

## Context
Extracted from task: [acceptance-fix] Monitoring lifecycle HTTP: skutečné bounded routes a funkční end-to-end ověření: go
