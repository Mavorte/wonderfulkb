---
title: "Preserve handoff snapshots and unrelated work during acceptance cleanup"
date: 2026-10-19
category: patterns
component: tooling
tags: [handoff, manifest, git-status, scope]
file_type: rules
---

# Preserve handoff snapshots and unrelated work during acceptance cleanup

All 28 handoff snapshots matched their manifest SHA-256 hashes after implementation. The working tree also contained unrelated untracked `opencode.json` and prior acceptance-run artifacts, which were left untouched. Reuse manifest hash checks to confirm handoff integrity, and inspect status before cleanup so unrelated user artifacts are not removed.

## Context
Extracted from task: Case Client: dokončit server UUID a odstranit projektové znečištění acceptance diffu
