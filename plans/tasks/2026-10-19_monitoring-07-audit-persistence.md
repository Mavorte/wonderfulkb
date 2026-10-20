---
title: "Monitoring: uložit idempotentní event deník s bounded dotazy"
type: implementation
---

# Monitoring: uložit idempotentní event deník s bounded dotazy

## Goal
Dodat otestovaný append-only auditní sink a bounded čtení podle doloženého journal access kontraktu.

## Files/functions
Nové `be-document-processing/src/document_processing/audit/audit_storage.py` a `audit_queries.py`, `be-document-processing/tests/test_monitor_audit_storage.py`; pouze auditní konfigurace/factory v `config.py`, `bootstrap.py`, existující `template.yaml` pokud kontrakt potřebuje definici auditního resource.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Vycházet z `plans/monitoring/journal-access-contract.md`, `audit_cursor.py` a `audit_events.py`. Deduplikovat event_id bez duplicitního přičítání, podporovat document-scope FileReceived, partial run bez úvodního eventu, audit-only identity a minimální odvoditelné indexy/revision s fencing. Runtime deník bez business kopií, navržená TTL nevymazává business ani korekce. Audit not_configured nepokouší čtení neexistující tabulky; konfigurovaný ale vadný zdroj je chyba, ne empty success. Tabulkové oddělení a least-scope resource/IAM návrh musí zůstat audit-only.

## Boundaries
Bez nasazení, migrace/replay, nového listener service, business zápisů a hooků. Žádný Scan nebo unbounded replay při pollu; event gap přiznat. Neměnit původní deník při tvorbě projekce. Použít uvedená domain-qualified jména modulů.

## Verification
pytest `be-document-processing/tests/test_monitor_audit_storage.py` přes Moto/fakes: duplicate event, reorder, partial run, late insert+refresh, token scope, více stránek, read failure, TTL a fence starého pokusu. Spy prokáže bounded Query a nulové business writes. Zachovat `test_aws_storage.py`; jeho pk/sk fixtures nejsou důkaz současného AWS business kontraktu.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
