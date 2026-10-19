---
title: "Static SAM checks cannot establish deployed gateway behavior"
date: 2026-10-19
category: tooling
component: ci-cd
tags: [sam, api-gateway, verification]
file_type: rules
---

# Static SAM checks cannot establish deployed gateway behavior

The offline suite passed handler integration tests and static checks of protected REST routes, API-key stage binding, gateway errors, and scoped permissions. However, AWS SAM CLI was unavailable, so `sam validate --lint --template-file be-case-client/template.yaml` was not run; deployment and cloud smoke tests were also not performed. API-key protection was therefore verified only in the template.

Keep verification claims tied to the layer actually exercised: static template assertions establish configuration intent, while SAM linting and deployed smoke tests provide additional evidence about template validity and runtime gateway behavior. Record missing tooling and the exact outstanding command in the handoff.

## Context
Extracted from task: Case & Client: jedna Lambda s explicitními mock daty, offline testy a minimálním SAM balením
