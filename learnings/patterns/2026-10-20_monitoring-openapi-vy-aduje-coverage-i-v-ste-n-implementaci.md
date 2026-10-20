---
title: "Monitoring OpenAPI vyžaduje coverage i v částečné implementaci"
date: 2026-10-20
category: patterns
component: backend
tags: [monitoring, openapi, schema]
file_type: rules
---

# Monitoring OpenAPI vyžaduje coverage i v částečné implementaci

OpenAPI kontrakt document-events uvádí `coverage=partial` jako povinné pole, přestože starý testovací sketch očekával jen tři pole. Při implementaci a aktualizaci testů vycházet z aktuálního kontraktu; nepřebírat očekávání ze starého sketchi.

## Context
Extracted from task: Monitoring HTTP: dokončit autentizovaný document-events základ a skutečné nasazení
