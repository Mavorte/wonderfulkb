---
title: "Plan monitoring contracts from approved path scope"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, openapi, planning, contract-tests]
file_type: rules
---

# Planning a contract-only monitoring revision

For a monitoring contract task, treat the existing OpenAPI document as a potentially over-broad proposal, not as permission to preserve every route it currently describes. Reconcile the exact approved path inventory against the slice briefs and lifecycle reducer brief before changing schemas. Keep the contract's required read scope explicit, and distinguish contract requirements from deployed route evidence. A focused offline test should assert both the positive path/schema allowlist and negative exclusions (business projections, artifact/content paths, and prohibited fields); resolve local `$ref`s so syntactic YAML validity alone cannot hide a broken contract.
