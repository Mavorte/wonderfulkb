---
title: "Keep page observation mapping pure and window-scoped"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, audit, observations, purity]
---

# Pure page-observation mapping stays bounded and content-free

For monitoring page reads, map only the finite, already validated observation window supplied by the caller. Require explicit run and positive attempt scope; reject malformed scope even when an observation would otherwise be filtered out. Preserve each observation in input order, including multiple outcomes for one page and terminal-only fragments.

Use per-event allowlists so page content, URLs, raw exceptions, and unrelated fields cannot escape. Cache reuse stays a separate observation with `cached_*` fields; it must never become a new completion or inference. Deep-copy nested allowlisted values such as opaque artifact ID lists so callers cannot mutate the source event through returned output.

When the target pytest file passes but the package-wide collection fails due to a separate owned test importing event classes absent from its module, report the focused result separately and retain the full-gate failure. Do not widen a mapper task into changes to the event module merely to manufacture a green gate.
