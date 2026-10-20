---
title: "Intake monitoring RED requires multipart and an explicit fixture import"
date: 2026-10-20
category: test-failures
component: backend
tags: [monitoring, pytest, fastapi, python-multipart, tdd]
file_type: rules
---

# Intake monitoring RED needs multipart and an explicitly imported fixture

In this checkout `be-intake/tests/test_monitor_file_received.py` declares `intake` inside that test module; there is no shared `conftest.py`. A new focused test can import it explicitly (`from test_monitor_file_received import intake`) rather than pretending fixture discovery crosses modules. The previous steps test declared `intake` without importing it, so its failure was fixture setup, not a behavioral RED.

`be-document-processing/.venv/bin/python` has pytest, FastAPI, boto3 and httpx, and `PYTHONPATH=be-document-processing/src` exposes the audit package. However, checking `import multipart` in that venv failed: `python-multipart==0.0.20` is required by `be-intake/app/requirements.txt` for the FastAPI upload route to load. Install the pinned intake test dependency into this project venv, verify collection and main import, then capture the missing-steps-route 404-vs-200 assertion with identical focused argv for RED and GREEN via skill:tdd. Keep the old failedinfra evidence untouched.
