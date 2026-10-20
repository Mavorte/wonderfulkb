---
title: "Stream template parity must use its canonical owner"
date: 2026-10-20
category: architecture
component: backend
tags: [cloudformation, dynamodb, template-parity, rollback]
---

# Keep stream-template parity anchored to its canonical owner

The validator trigger's canonical DynamoDB table template lives at `be-intake/documents-table/template.yaml`. From `be-validator-agent/trigger/tests/test_template.py`, the repository root is `HERE.parents[1]`; `HERE.parents[2]` escapes the checkout and produces a misleading `FileNotFoundError`.

For stream-copy parity, remove only `DocumentsTable.Properties.StreamSpecification` and compare the complete resource maps. Check that all canonical outputs remain and only `StreamArn` may be added. This detects accidental loss of independent audit resources and outputs as well as changes to retention, PITR, tags, encryption, and keys.

Rollback paths should be anchored after the deploy script changes into its own directory, then resolve the canonical owner path there. This keeps execution independent of the caller's working directory.
