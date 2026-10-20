---
title: "Validate the installed image independently of source-level tests"
date: 2026-10-20
category: tooling
component: backend
tags: [docker, packaging, wheel, smoke-test, provenance]
file_type: rules
---

# Validate the installed image independently of source-level tests

The Python suite passed with 504 tests, but delivery verification also exercised the final amd64 image using a non-editable wheel, UID 10001, and disabled networking. This checks the packaged runtime rather than relying solely on tests against the working tree. Reuse an installed-image smoke test and record artifact digests so deployment handoff identifies the exact verified artifact. Keep image verification distinct from deployment verification: the currently deployed image still lacked the signature steps allowlist.

## Context
Extracted from task: Monitoring MVP: detekce podpisů ve stávajícím steps API
