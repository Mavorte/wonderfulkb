---
title: "Monitoring OpenAPI contracts need semantic validation"
date: 2026-10-20
category: test-failures
component: backend
tags: [openapi, yaml, pytest, contract-tests]
file_type: checklist
---

# OpenAPI observation contracts: validate both YAML and OpenAPI semantics

For contract-only changes, PyYAML parsing and resolving every local `$ref` are necessary but not sufficient. A syntactically parseable YAML file can still encode the wrong OpenAPI object—for example, an unquoted colon in a flow-style `description` can become a new mapping key and invalidate an `apiKey` security scheme.

Use the repo-local interpreter for parse/ref checks, then run the already-installed `openapi_spec_validator.validate_spec` on the parsed document. Keep response objects explicit per status, reference reusable response components, and verify that each referenced response contains its private cache header. For event union tests, resolve each `$ref` branch before inspecting the type discriminator and `additionalProperties`; don't assume inline schemas.

The focused pytest collection is valuable independently of the package-wide run: a collection error from unrelated incomplete tests (such as an absent event symbol import) should be reported precisely without concealing it or changing its assertions to get a green suite.
