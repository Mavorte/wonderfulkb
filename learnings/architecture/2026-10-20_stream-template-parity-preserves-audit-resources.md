---
title: "Stream template parity preserves audit resources"
date: 2026-10-20
category: architecture
component: backend
tags: [cloudformation, dynamodb, stream, audit, rollback]
file_type: rules
---

# Stream template parity needs whole-template accounting

The DynamoDB documents table's canonical CloudFormation template is owned by `be-intake/documents-table/template.yaml`. A consumer's stream-enabled copy must preserve every canonical resource and output, including the separate `AuditTable`, its retention/encryption settings, and audit outputs. Normalize only `DocumentsTable.Properties.StreamSpecification` when asserting resource parity, and allow only the intentional additional `StreamArn` output. Resolve rollback paths from the script's own working directory to the canonical owner rather than assuming a sibling `documents-table/` directory exists.
