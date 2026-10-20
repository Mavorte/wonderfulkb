---
title: "Další TDD cyklus zachová původní skutečný RED a GREEN"
date: 2026-10-20
category: tooling
component: tooling
tags: [tdd, proof, acceptance, provenance]
file_type: rules
---

# Starting a genuine follow-on TDD cycle under the same task

The supported tdd proof-capture helper accepts GREEN after the matching RED. Calling green again on a completed proof can reject before child launch with a malformed phase-structure diagnostic; this does not mean the previously accepted evidence should be edited. Read the canonical proof and preserve actual run IDs/results.

When a new missing behavior is discovered, write its failing test and use red --start-new-cycle -- with the same focused argv. The helper validates and archives the entire previous RED/GREEN bytes into plans/checkpoints/<task-id>.cycles/, then captures a new actual RED. Verify accepted_red and child exit1 before the new production change. Capture matching GREEN through the helper and link both canonical and archived cycles in task-local evidence. Never delete working implementation to force RED or manually rebuild historical proof.

In task task-cf441015-6bba-4862-8200-b2c0047f6905 the original route401-to200 proof and34-pass GREEN were preserved, while new actual public-DTO schema failures received their own genuine RED and52-pass GREEN. Historical failed/partial broad runs remained recorded rather than relabelled as the latest result.