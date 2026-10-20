---
title: "Missing trusted authorization must prevent audit reads"
date: 2026-10-20
category: security-issues
component: backend
tags: [authorization, monitoring, audit, fail-closed]
file_type: rules
---

# Missing trusted authorization must prevent audit reads

The lifecycle routes were implemented locally, but intake still lacked a trusted provider mapping the caller to authorized cases and documents. Without that provider, the routes returned HTTP 403 without reading audit data. Preserve this fail-closed behavior: establish trusted resource authorization before any audit read, and treat a missing provider as a functional deployment blocker.

## Context
Extracted from task: [acceptance-fix] Monitoring lifecycle HTTP: skutečné bounded routes a funkční end-to-end ověření: go
