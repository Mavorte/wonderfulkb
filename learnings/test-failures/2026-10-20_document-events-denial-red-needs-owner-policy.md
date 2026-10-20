---
title: "Acceptance repair: document-events RED musí rozlišit policy od chybějící route"
date: 2026-10-20
category: test-failures
component: backend
tags: [monitoring, authorization, tdd, acceptance]
file_type: rules
---

# Acceptance repair: distinguish absent route RED from denied-case policy

For WonderfulKB document-events planning, the existing `be-intake/tests/test_processing_monitor_routes.py` sketch asserts 200 with only `x-api-key`, lacks the explicit import of `intake` from `test_monitor_file_received`, and omits the contract-required `coverage: partial`. A fixture setup error cannot prove RED, and a shared-key success cannot prove case entitlement.

First establish the owner-approved principal→case decision and authenticated synthetic fixture. Then a focused, executable RED can assert a defined denial response on the document-events path: before route registration FastAPI returns generic 404; after implementation it returns the owner-approved 403 or masked-404 body without audit reads. The same focused command must also exercise authorized document membership and bounded paging before GREEN. Keep parent failed evidence intact and create proof under the follow-up task ID.
