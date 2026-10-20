---
title: "Signature observations and public failure codes require separate contract coverage"
date: 2026-10-20
category: patterns
component: backend
tags: [monitoring, signature, api-contract, allowlist]
file_type: rules
---

# Signature observations and public failure codes require separate contract coverage

The existing steps GET needed to expose `signature_detection` observations for `StepStarted`, `StepFinished`, and `StepFailed`, while document/run events also had to preserve the public failure code `SIGNATURE_DETECTION_FAILED`. Extending the step allowlist alone would not establish the full public contract. Reuse focused coverage across lifecycle observations and failure-code projection, and update the canonical OpenAPI contract and image smoke checks together. Preserve bounded queries, authorization/scope checks, continuation behavior, and payload privacy restrictions.

## Context
Extracted from task: Monitoring MVP: detekce podpisů ve stávajícím steps API
