---
title: "Audit event durations in DynamoDB"
date: 2026-10-20
category: database-issues
component: backend
tags: [audit, dynamodb, serialization, testing]
---

# DynamoDB audit duration serialization

When audit events accept a measured fractional `duration_ms`, convert it to `Decimal(str(value))` in the event's explicit DynamoDB `to_item()` serializer. boto3 rejects binary float values as DynamoDB numbers, and the audit store intentionally catches serialization errors and returns `unavailable`, which can otherwise hide the specific cause. During `from_item()`, convert stored `Decimal` duration back to float for stable event equality. Keep this change scoped to the new event contract so existing event serialization remains unchanged.

For lifecycle contracts, focused Moto coverage should include both event document writes and reads: a class contract test passing does not exercise DynamoDB's numeric type restrictions or decoder round-trip.
