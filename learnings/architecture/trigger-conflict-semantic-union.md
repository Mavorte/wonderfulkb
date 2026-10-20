---
title: "Trigger integration conflicts: preserve lifecycle and execution features"
date: 2026-10-20
category: architecture
component: backend
tags: [trigger, conflicts, execution-ledger, audit, webhook]
---

# Resolving trigger integration conflicts as a semantic union

When integrating the WonderfulKB trigger lifecycle/webhook work with execution-ledger/audit work, preserve both branches' contents within each conflict region rather than accepting one side wholesale. The package staging lists must include lifecycle handlers (`case_step`, `wonderful_webhook`) and execution modules, while the package also needs the audit package synchronized into both light and worker layouts.

In `Context`, retain case and execution table names and lazily initialize the audit listener. In the SAM template, case and execution/audit IAM statements belong together in their respective function policy; repeated `Sid` values across distinct policy blocks are valid. Tests need both the cases table (single `case_id` hash key) and execution ledger table (`pk` hash / `sk` range).

For this mechanical repair, the supplied offline checks are effective: `bash -n`, marker scanning, side-effect-free `ast.parse`, and the existing moto-backed pytest suite verify the merge without invoking build or cloud operations.
