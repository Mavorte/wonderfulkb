---
title: "Separate global and client-scoped case listing"
date: 2026-10-19
category: architecture
component: backend
tags: [case-client, dynamodb, pagination, api]
file_type: rules
---

# Separate global and client-scoped case listing

Global `GET /cases` cannot reuse a client-scoped listing helper by passing `None`: that path reads client context and queries a GSI. Give global listing its own repository port and cases-table Scan, with a cursor fingerprint distinct from the client-scoped cursor. If the response limit is reached partway through an SDK page, resume from the last case ID returned; using `LastEvaluatedKey` there would skip the unreturned records in that page. Keep response projection in the handler and protect the new route with the same API-key mechanism as the existing routes.

## Context
Extracted from task: [acceptance-fix] Case Client: GET /cases napříč všemi klienty: goal-001: Case Client: GET /cases nap
