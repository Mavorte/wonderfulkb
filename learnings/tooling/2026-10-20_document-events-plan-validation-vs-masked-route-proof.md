---
title: "Document-events plán: validní artefakt a masked-404 důkaz jsou různé brány"
date: 2026-10-20
category: tooling
component: tooling
tags: [compound-plan, monitoring, authorization, tdd, acceptance]
file_type: rules
---

Pro task-cf441015-6bba-4862-8200-b2c0047f6905 prošel inspect_plan_artifact po opravě H1 na # Plan 2026-10-20: název; samotné platné sekce nestačily. Volání používá projektový be-document-processing/.venv/bin/python, PYTHONPATH k workspace/km-system/lib a task kontext s projectDir. Výsledek valid dokládá pouze plán, nikoli implementaci nebo TDD. V plánovaném focused testu document-events musí masked 404 rozlišit existující autorizovanou route od obecné odpovědi pro chybějící route: ověřit registraci přesného GET, denial politiku a nulové audit reads. Ani tato negativní větev nenahrazuje autorizovaný FileReceived DTO, scoped pagination a live-function evidence. Zachovat původní proof historii a případné chybějící owner entitlement/fixture vést jako blocker.