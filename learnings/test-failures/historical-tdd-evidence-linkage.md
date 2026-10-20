---
title: "Historical TDD evidence needs an explicit linkage mode"
date: 2026-10-20
category: test-failures
component: tooling
tags: [tdd, proof, acceptance, provenance]
file_type: rules
---

# Historical TDD evidence needs an explicit linkage mode

The proof-capture helper accepts GREEN only when this task already has a helper-captured RED with matching task ID and command. A valid RED/GREEN artifact from a parent task cannot be linked or imported using the current workflow.

For an evidence-only follow-up where the implementation already passes, do not manufacture a new RED or hand-write a proof artifact. Capture ordinary fresh verification as directed, preserve the historical proof unchanged, and report the provenance limitation until a supported linkage contract exists.
