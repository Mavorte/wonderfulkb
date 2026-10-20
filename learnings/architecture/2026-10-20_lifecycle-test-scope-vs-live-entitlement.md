---
title: "Lifecycle route plan: fake scope tests cannot establish deployment entitlement"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, lifecycle, authorization, planning]
file_type: rules
---

In lifecycle HTTP acceptance repair, a TestClient fake for a trusted scope provider is suitable for proving one bounded reader call and reducer mapping, but it cannot establish production caller-to-case entitlement. The ingest service currently authenticates one global x-api-key and require_case checks only existence; the live route must be gated on an owner-confirmed identity-to-case policy plus document membership lookup. Preserve the prior 403 proof, capture functional 200 GREEN separately, and verify the installed revision with a legitimately entitled fixture before labeling the route delivered.