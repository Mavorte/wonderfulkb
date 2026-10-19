---
title: "Case Client: source kontrakt a lokální acceptance noise"
date: 2026-10-19
category: tooling
component: backend
tags: [case-client, planning, tdd, gitignore, acceptance]
file_type: rules
---

# Case Client: source contract versus local acceptance noise

When preparing a source-only UUID migration, inspect the implementation even if OpenAPI already says 1.4.0: the handler can still require caller `case_id` and return replay 200. Treat an existing failing assertion as a fresh RED only after verifying the selected interpreter/dependencies, then capture a new root-specific RED/GREEN with identical focused argv; historical proof belongs to its original task.

For acceptance diff hygiene, root `.gitignore` and `.git/info/exclude` can mask each other. Validate root ignore rules against an isolated fixture containing only the root ignore file, including negative checks for source and plans, before trusting untracked-file counts. Do not delete generated artifacts or mutate `.git` to hide them.
