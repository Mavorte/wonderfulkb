---
title: "Processing Monitor: focused test fixture and missing route foundation"
date: 2026-10-20
category: test-failures
component: backend
tags: [pytest, fastapi, monitoring, authorization]
---

## WonderfulKB monitoring route test setup

The route tests in `be-intake/tests/test_monitor_file_received.py` declare an `intake` pytest fixture locally, so it is unavailable to new test modules. There is also no `conftest.py` in `be-intake/tests`. Before adding a focused module, move/re-export the fixture through a shared conftest or explicitly import the fixture module; otherwise pytest reports “fixture 'intake' not found,” which is a collection/setup error and not a meaningful RED for the behavior under test.

The checked-out intake `main.py` currently only has upload/document-list routes. The Processing Monitor route modules and trusted case/document authorization seam described by the contract are absent, even though the page mapper and OpenAPI specification exist. A safe implementation must first restore/identify that established shared reader and authorization foundation rather than inventing a key-based case authorization fallback.
