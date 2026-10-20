---
title: "Bounded lifecycle reducer identity and evidence"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, lifecycle, evidence, identity]
---

# Bounded lifecycle reducer identity rules

Attempt terminal observations without `run_id` can be retained as unscoped evidence without fabricating a run or attempt summary. For `AttemptStarted`, validate supplied canonical and compatibility ordinal fields together: a disagreement is uncertainty, and must not allow a legacy value to select a different attempt. Keep distinct event identities and distinct attempt ordinals independent; only a repeated `(event_id, sequence)` carrying a different payload is an identity conflict. Conflict evidence must be retained at the summary boundary, including when the payload changes run or attempt scope.

Capture focused pytest RED/GREEN through the TDD proof helper using the exact same argv; a failed GREEN attempt remains diagnostic and can be corrected before the accepted GREEN is published. Verify the complete proof file and then run the wider backend and registered app gates.
