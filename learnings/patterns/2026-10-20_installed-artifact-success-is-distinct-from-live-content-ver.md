---
title: "Installed-artifact success is distinct from live content verification"
date: 2026-10-20
category: patterns
component: backend
tags: [verification, fixtures, deployment, monitoring]
file_type: rules
---

# Installed-artifact success is distinct from live content verification

The attempts endpoint passed source tests and installed-image smoke, while App Runner still served the previous run-events image. Nonempty live verification also lacked a documented, currently authorized fixture containing a real `AttemptStarted`. Refreshed worker environment variables removed an earlier configuration blocker but did not prove that a producer had emitted the required event. Track SOURCE, INSTALLED, DEPLOYED, and LIVE-FUNCTION-VERIFIED as separate evidence states, refresh historical blocker claims against current runtime configuration, and require an authorized real-event fixture for nonempty live proof.

## Context
Extracted from task: Monitoring MVP: jeden GET pozorovaných pokusů
