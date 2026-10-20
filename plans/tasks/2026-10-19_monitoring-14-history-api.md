---
title: "Monitoring: číst audit, runy a timeline ze stejného deníku"
type: implementation
---

# Monitoring: číst audit, runy a timeline ze stejného deníku

## Goal
API vrací pravdivé bounded audit/run/attempt/step/page/event DTO a run events jsou filtrovaný výřez dokumentového deníku.

## Files/functions
`be-document-processing/src/document_processing/audit/audit_queries.py`, `processing_monitor_routes.py`, `processing_monitor_business.py`; nové `be-document-processing/tests/test_monitor_history_api.py`; bezpečné proxy rozšíření backoffice functions ve stávajícím vzoru.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Implementovat zbývající audit/history cesty OAS kromě artifacts přes `plans/monitoring/journal-access-contract.md`. Dokument events obsahuje FileReceived bez runu; run events jen stejný journal filtrovaný run_id. Bounded list runů musí přiznat partial bez RunQueued. Steps/pages vyžadují attempt_no; neznámý run/pokus=404. observed_at je čas čtení, nullable activity/measurement nejsou nula. availability/coverage/freshness a scoped revision nezaměnit za business status, heartbeat nebo úplnost. audit-only identitu zapojit do business union.

## Boundaries
Žádné nové auditní kopie business, CURRENT duplicity bez doložené potřeby ani full replay při pollu. Not_configured/not_instrumented ≠ prázdná historie; read error=503. Zachovat case/content auth, server-only secret a private,no-store, bez dnešního obsahu vydávaného za historický.

## Verification
pytest `be-document-processing/tests/test_monitor_history_api.py` a backoffice proxy testy: legacy, skutečně empty, source failure, FileReceived-only, partial run, více pokusů, duplicate/gap/reorder/late event+refresh, neplatný attempt, cross-case a token binding. Assert kontrakt všech history cest a stejná event_id pro document/run výřez, bounded počet queries a správné page outcome counts.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
