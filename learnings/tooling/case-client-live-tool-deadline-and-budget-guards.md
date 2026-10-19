---
title: "Case Client live-tool deadline and budget guards"
date: 2026-10-19
category: tooling
component: backend
tags: [case-client, deadline, rate-limit, live-evidence, rollback]
file_type: rules
---

# Case Client live-tool deadline and budget guards

The HTTP runner's total deadline must be rechecked after waiting for a shared rate-limit slot. Calculate the request timeout from the remaining deadline only after that wait; otherwise the transport can initiate a request after the permitted window or let its fixed timeout overrun the run budget.

For an explicitly authorized continuation, key the narrower budget by its continuation identity: deny forward work at the deadline, cap forward deploy operations while preserving one distinct recovery slot, and cap POST attempts independently. Keep tests offline with a fake clock and mocked opener. Do not interpret passing offline guard tests as authorization or evidence for live deployment/HTTP writes.
