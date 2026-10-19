---
title: "Interpreter availability does not establish a usable Python test environment"
date: 2026-10-19
category: tooling
component: backend
tags: [python, venv, ensurepip, dependencies, tdd]
file_type: rules
---

# Interpreter availability does not establish a usable Python test environment

Python 3.13 was available, but creating an isolated virtual environment failed during `ensurepip`. The base interpreter also lacked `boto3` and `simplejson`, preventing component-test verification. No environment repair was demonstrated in this run.

Preflight the complete environment bootstrap—virtual environment creation, pip availability, and dependency installation—rather than checking only the Python version. A bootstrap or missing-dependency failure is not a valid TDD RED: capture RED only after the intended test executes and fails for the behavior under development.

## Context
Extracted from task: Case & Client: nasadit náš Python na existující testovací API a odladit živou DB integraci
