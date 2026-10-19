---
title: "TDD proof helper rejects an existing cycle"
date: 2026-10-19
category: tooling
component: tooling
tags: [tdd, proof-capture, workflow]
---

# TDD proof helper cycle validation

When continuing an implementation whose canonical proof already has a RED and GREEN, `proof-capture.py red --start-new-cycle` first validates the prior proof and archives it. The helper can reject a previously accepted proof as structurally incomplete. In that case it leaves the canonical proof untouched; do not manually reconstruct or overwrite it. Preserve the diagnostic and resolve validation before producing source changes that require accepted RED proof.
