---
title: "Lifecycle reducer requires canonical attempt ordinals"
date: 2026-10-20
category: architecture
component: backend
tags: [lifecycle, audit, canonical-identity, tests]
file_type: rules
---

# Canonical attempt ordinals only

The lifecycle reducer must not treat `attempt_number` or `attempt_id` as an ordinal. Only a positive integer `attempt_no` can group attempt observations. Tests that characterize supported attempt grouping should therefore use `attempt_no`; alias-only events should remain without a definite attempt summary.

When changing this contract, update older fixture events as well as adding negative alias-only regressions. Otherwise unrelated reducer behavior tests may fail merely because they still encode the retired alias contract.
