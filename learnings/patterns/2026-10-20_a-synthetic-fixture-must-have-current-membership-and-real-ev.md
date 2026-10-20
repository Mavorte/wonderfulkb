---
title: "A synthetic fixture must have current membership and real event evidence"
date: 2026-10-20
category: patterns
component: e2e
tags: [synthetic-fixture, monitoring, live-verification, scope]
file_type: rules
---

# A synthetic fixture must have current membership and real event evidence

Positive live HTTP verification was blocked because the designated synthetic document lacked current metadata membership and its bounded audit query returned no records. No actual signature event, run, or attempt was established. Before using a synthetic document for end-to-end proof, verify its current scoped membership and the existence of the relevant event/run/attempt through the supported bounded reads. A known fixture identifier alone is insufficient evidence that the runtime scenario is available.

## Context
Extracted from task: Monitoring MVP: detekce podpisů ve stávajícím steps API
