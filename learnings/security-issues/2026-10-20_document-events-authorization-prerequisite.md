---
title: "Monitoring: oprávněný case musí mít doloženou identitu a autorizační rozhodnutí"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, authorization, tdd, intake]
file_type: rules
---

V intake `guard()` ověřuje pouze sdílený `x-api-key`; `require_case()` zjišťuje existenci řádku case pouze pro upload. `test_monitor_file_received.py` mockuje existující case, nikoli oprávněného volajícího. Ani úspěšná auditní sada (209 testů) proto neprokazuje, že lze bezpečně zpřístupnit case-scoped monitoring GET. Existující `processing_monitor_lifecycle_routes.py` explicitně vrací 403, dokud vlastník nedodá důvěryhodnou identitu volajícího a rozhodnutí identity→case. Pro document-events nejdřív získat tento owner interface, denial/read-error politiku a autentizovanou syntetickou fixture; teprve pak zachytit smysluplné TDD RED/GREEN a nasadit. Chybějící pytest fixture ve starém sketchi je collection/setup chyba, nikoli behavioral RED. OpenAPI uvádí coverage=partial jako povinné pole, i když starý sketch očekává jen tři pole.