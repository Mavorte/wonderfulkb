---
title: "Monitoring event HTTP: odlišit návrh OpenAPI od reálného řazení auditního store"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, openapi, audit, pagination, planning]
file_type: rules
---

Při plánování document-events HTTP v WonderfulKB porovnej jediný `be-document-processing/contracts/openapi-processing-monitor.yaml` se skutečným `be-document-processing/src/document_processing/audit/audit_queries.py` a test sketch v `be-intake/tests/test_processing_monitor_routes.py`. YAML požaduje `coverage: partial` navíc k `items,next_token,observed_at`, ale sketch kontroluje přesně jen tři klíče. Auditní Query pokračuje podle `pk/sk` (`EVENT#event_id`), takže bez změny readeru nelze slibovat stabilní server-side `occurred_at,event_id` globální pořadí. Zaznamenej přesný rozpor před testy a nemaž `coverage` ani nevyráběj neomezené řazení historie kvůli zdánlivé shodě. AuditStore.read_document již zajišťuje bounded read; chybu nepřevádět na prázdné položky. Samotný sdílený API klíč a existence case nepotvrzují caller→case autorizaci.