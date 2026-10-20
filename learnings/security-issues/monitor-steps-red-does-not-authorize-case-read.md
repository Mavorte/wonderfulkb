---
title: "Monitor steps HTTP: behaviorální RED nenahrazuje autorizaci case"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, fastapi, authorization, tdd]
file_type: rules
---

# Monitor steps HTTP: behaviorální RED nestačí jako oprávnění ke GREEN

Ve WonderfulKB `be-intake/app/main.py` ověřuje middleware pouze globální `x-api-key`; `require_case()` kontroluje existenci case jen na upload path. Skutečná autorizace konkrétního volajícího ke case a membership documentu zde není. `audit_queries.read_document()` omezuje Query a váže dokumentový cursor, ale token ani existence case nedávají caller→case oprávnění. Ani deklarace route v OpenAPI není implementace.

Při TDD nejprve explicitně importovat lokální `intake` fixture z `test_monitor_file_received.py`, do projektového venv nainstalovat chybějící `python-multipart==0.0.20` a ověřit pytest collection. Teprve pak helper `skill:tdd` zachytí skutečný behaviorální RED (existující FastAPI odpovídá 404 na očekávaný steps GET). Bez trusted identity, entitlement checku, document-in-case lookupu a 403/404 politiky nelze bezpečně přidat route ani získat poctivý GREEN pomocí shared-key mocku; proof se ponechá RED-only a deployment se nespouští. Zaznamenat SOURCE/INSTALLED/DEPLOYED/LIVE odděleně, včetně skutečného blockeru a stavu regresních gate.
