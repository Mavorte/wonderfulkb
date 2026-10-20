---
title: "Auditní TDD roundtrip: pořadí Query je podle event_id"
date: 2026-10-20
category: test-failures
component: backend
tags: [audit, tdd, dynamodb, query, planning]
file_type: rules
---

Při návrhu Moto RED/GREEN testu `AuditStore.read_document` ve WonderfulKB nepředpokládej řazení podle `occurred_at` ani `sequence`: document Query vrací položky seřazené podle sort key `EVENT#<event_id>`. Chceš-li testovat přesnou posloupnost `[started, finished]`, zvol stabilní `event_id` jako `evt-regression-1-start` a `evt-regression-2-finish`, jinak bude test po správné implementaci falešně červený. Alternativně porovnej mapu podle event_id, pokud pořadí není součástí testované vlastnosti. Pro skutečnou roundtrip chybu nejprve assertuj `put(...) == "inserted"`, pak třídu, rovnost a číselné typy přečtených událostí.