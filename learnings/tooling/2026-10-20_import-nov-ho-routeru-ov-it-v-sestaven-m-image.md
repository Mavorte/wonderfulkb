---
title: "Import nového routeru ověřit v sestaveném image"
date: 2026-10-20
category: tooling
component: backend
tags: [docker, packaging, smoke-test]
file_type: rules
---

# Import nového routeru ověřit v sestaveném image

Dockerfile kopíroval aplikační soubory explicitně, takže nový `processing_monitor_lifecycle_routes.py` musel být přidán do `COPY`. Po sestavení image prošel smoke test importu `main`, routeru i audit package a potvrdil registraci tří routes. U nových modulů v takovém balení opakovat import test přímo v image; lokální testy samy neověří obsah výsledného artefaktu.

## Context
Extracted from task: Monitoring lifecycle HTTP: skutečné bounded routes a funkční end-to-end ověření
