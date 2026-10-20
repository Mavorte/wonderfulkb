---
title: "Monitoring: zpřístupnit bezpečný list a detail přes backoffice proxy"
type: implementation
---

# Monitoring: zpřístupnit bezpečný list a detail přes backoffice proxy

## Goal
Autorizovaný uživatel otevře case-scoped list/detail současných dokumentů přes existující serverovou cestu; jiný case ani artefakt nezíská.

## Files/functions
Nové `be-document-processing/src/document_processing/processing_monitor_routes.py` a `processing_monitor_access.py`, `be-document-processing/tests/test_monitor_access.py`; zapojení v `api.py`. Backoffice `functions/lib/awsApi.ts` a nové domain-named proxy function dle stávajícího case-get vzoru; testy vedle proxy.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Spotřebovat mapování `processing_monitor_business.py` a konkrétní trust/case/content kontrakt z `plans/monitoring/producer-contract.md`. Implementovat pouze GET collection/detail pod /v1/cases/{case_id}/processing/documents podle OAS, prefix /v1 přesně jednou. Zachovat stávající credential server-only a ověřit skutečné uživatelské právo ke case; API key sám právo není. Nenahrazovat chybějící trusted identity query/headerem od browseru; chybějící důvěryhodný zdroj je konkrétní technický blocker. 404 absence, 403 nebo konzistentně maskovaná 404 nepřístupného case, 503 výpadek; private,no-store.

## Boundaries
Bez změn ostatních business endpointů, broad IAM či nové služby. Historické endpointy/obsahy zatím nevystavovat. Žádná credentials v bundle/logu, žádné inference/cloud volání při testech.

## Verification
pytest `be-document-processing/tests/test_monitor_access.py` a `pnpm -C apps/backoffice test`: cross-case identity, podvržený case scope, chybějící trust, timeout/503, token binding a hlavičky. Zachovat existující case-get testy. Proxy nepropouští interní bucket/key, provider chybu ani serverový klíč.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
