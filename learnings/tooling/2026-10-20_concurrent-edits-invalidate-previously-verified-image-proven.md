---
title: "Concurrent edits invalidate previously verified image provenance"
date: 2026-10-20
category: tooling
component: backend
tags: [docker, concurrency, provenance, smoke-tests]
file_type: rules
---

# Concurrent edits invalidate previously verified image provenance

After the attempts GET passed genuine RED/GREEN testing and an initial Docker build/smoke, concurrent signature-allowlist changes landed in the shared facade, step router, YAML, and smoke test. A hash readback revealed that the existing image no longer matched the final source. Preserve concurrent changes, rebuild the final image, and rerun the installed ASGI smoke under production-like constraints; this run passed as UID 10001 without network access, followed by a broader gate of 709 passed and 1 skipped. Record original and final image-index, runnable-manifest, config, wheel, and source hashes separately so evidence identifies the exact artifact tested.

## Context
Extracted from task: Monitoring MVP: jeden GET pozorovaných pokusů
