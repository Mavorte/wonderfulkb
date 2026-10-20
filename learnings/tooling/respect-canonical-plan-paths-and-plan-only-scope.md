---
title: "Respect canonical plan paths and plan-only scope"
date: 2026-10-20
category: tooling
component: tooling
tags: [compound-plan, task-scope, planning]
---

Planning tasks with a mandated canonical path should resolve that path before creating any plan content. Preserve the caller's exact task ID, title, project root, and `--touch` arguments; then write only to the returned path. When the request is explicitly plan-only, do not perform implementation or deployment even if the plan describes those future acceptance requirements.
