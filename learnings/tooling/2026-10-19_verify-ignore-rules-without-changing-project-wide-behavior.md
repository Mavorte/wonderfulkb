---
title: "Verify ignore rules without changing project-wide behavior"
date: 2026-10-19
category: tooling
component: tooling
tags: [gitignore, acceptance-diff, generated-files]
file_type: rules
---

# Verify ignore rules without changing project-wide behavior

The required generated paths were already covered by the root `.gitignore`. An isolated fixture verified that generated files were ignored while source and evidence paths remained visible, so the existing ignore rules were preserved. Reuse a focused fixture when checking ignore behavior; avoid broad ignore-rule changes that could hide acceptance evidence or unrelated source.

## Context
Extracted from task: Case Client: dokončit server UUID a odstranit projektové znečištění acceptance diffu
