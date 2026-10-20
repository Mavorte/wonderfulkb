---
title: "Monitoring: prokázat bounded cursor a refresh opožděných událostí"
type: implementation
---

# Monitoring: prokázat bounded cursor a refresh opožděných událostí

## Goal
Dodat otestovaný technický access pattern event deníku, který při stránkování ani pozdějším refreshi trvale neskryje opožděný event.

## Files/functions
Nové `be-document-processing/src/document_processing/audit/audit_cursor.py`, `be-document-processing/tests/test_monitor_cursor.py`, `plans/monitoring/journal-access-contract.md`; lze upřesnit pouze dotčené paging/refresh části návrhového YAML a API průvodce.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Zachovat veřejné timeline řazení occurred_at,event_id, bez recorded_at. Vybrat konkrétní partition/sort/index a scope-bound opaque token, revision/fencing a postup UI refreshu včetně události vložené za již přečtenou časovou hranici. sequence je technické pořadí, ne důkaz kauzality/úplnosti. Doložit bounded Query a práci/paměť na request, run filtr, partial run bez RunQueued, audit-only identity, expiry a retenci. Sepsat přesný algoritmus i cenu případného minimálního runtime indexu; veřejné DTO se nemění na interní items.

## Boundaries
Jen čistý cursor/fixture prototyp, žádná skutečná persistence, producer hooky, cloud či změny business schémat. Žádný table Scan, neomezené přehrání celého deníku při pollu, pevné overlap okno vydávané za záruku pro libovolně pozdní událost ani domyšlená úplnost.

## Verification
pytest `be-document-processing/tests/test_monitor_cursor.py`: dvě stránky, stejné timestampy, mezery, opakovaný event, vložení staršího occurred_at mezi stránkami a po terminal, refresh, změna scope/filtru, vadný/expirující token, chybějící RunQueued a TTL. Testovat počty dotazů i konečnou dohledatelnost, ne jen výsledný snapshot. Dodat source-only kontrakt, nikoli tvrzení o živé DynamoDB.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
