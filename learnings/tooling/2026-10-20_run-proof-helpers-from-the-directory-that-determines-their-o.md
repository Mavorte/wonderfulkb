---
title: "Run proof helpers from the directory that determines their output path"
date: 2026-10-20
category: tooling
component: tooling
tags: [proof-artifacts, working-directory, acceptance]
file_type: rules
---

# Run proof helpers from the directory that determines their output path

The proof helper was launched from the backend subtree and wrote its artifact beneath that subtree, but acceptance required a monorepo-level `plans/checkpoints/...` path. A later root-level capture did not recreate the RED/GREEN proof because the tests already passed. Before running proof tooling, verify how its working directory determines output paths and confirm the artifact exists at the exact required location while the RED/GREEN sequence can still be captured. Do not treat a misplaced artifact as satisfying acceptance.

## Context
Extracted from task: Monitoring cache reuse: dokončit požadovanou validační, izolační a fail-open test matici
