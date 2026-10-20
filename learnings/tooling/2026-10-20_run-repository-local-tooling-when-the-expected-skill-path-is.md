---
title: "Run repository-local tooling when the expected skill path is absent"
date: 2026-10-20
category: tooling
component: tooling
tags: [save-learning, path, fallback]
file_type: rules
---

# Run repository-local tooling when the expected skill path is absent

The learning-save command first tried `.claude/skills/save-learning/add-frontmatter.py`, which did not exist in the project checkout. Running the installed helper at `/Users/michal/.config/opencode/skills/save-learning/add-frontmatter.py` succeeded. When a repository-local helper path is missing, locate and use the installed skill helper rather than treating the save operation as complete.

## Context
Extracted from task: [acceptance-fix] Monitoring worker: dokončit skutečná producer volání a behaviorální důkaz: goal-001
