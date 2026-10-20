---
title: "Stream template parity planning checks"
date: 2026-10-20
category: architecture
component: backend
tags: [cloudformation, dynamodb, stream, audit, rollback, testing]
file_type: rules
---

# Planning parity checks for stream-enabled templates

When planning template-parity repairs, compare the complete canonical resource set and outputs. Normalize only the intended stream property on the stream-enabled resource; permitting exclusions for audit resources can hide lost retention, encryption, and audit outputs. Keep rollback references anchored to the owning script's location and verify path resolution offline before any deployment.
