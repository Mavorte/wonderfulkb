---
title: "Monitoring: sjednotit read-only upload a analysis pohled"
type: implementation
---

# Monitoring: sjednotit read-only upload a analysis pohled

## Goal
Dodat bezpečné business DTO a stránkovaný union současných dokumentových zdrojů bez auditních zápisů.

## Files/functions
Nové `be-document-processing/src/document_processing/processing_monitor_business.py`, `be-document-processing/tests/test_monitor_business.py`; read-only AWS kontrakt a API průvodce. Vstupní seam viz `plans/monitoring/producer-contract.md`.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Implementovat explicitní safe mapping tabulek wonderfulkb-uw-documents a wonderfulkb-uw-document-analysis s `(case_id,document_id)`, nikoli pk/sk z historického source. List/detail spojovat podle identity, řadit document_id, deduplikovat matched/upload_only/analysis_only; připravit seam pro audit-only identity z journal access kontraktu. Filtr processing_status je současný analysis stav. Merge token musí nést pozice i zbytkový buffer všech zdrojů a scope/filtry/expiraci; prázdná stránka může mít pokračování. Unknown atributy vynechat, známé null a neznámý status zachovat podle OAS.

## Boundaries
Žádné změny business tabulek/ID, raw Dynamo dump, kopírování do auditu, full table Scan ani transakční snapshot slib. Zatím žádné HTTP/proxy/UI ani produkční přístupy. Nenakonfigurovaný audit je unavailable, konfigurovaný rozbitý zdroj není prázdný seznam.

## Verification
pytest `be-document-processing/tests/test_monitor_business.py`: syntetické přesné AWS shapes, chybějící volitelné atributy, union duplicity, multi-page a prázdná stránka s tokenem, filtry, scope tokenu, potvrzená absence vs výpadek (503 na service seam). Spy dokládá nulové business zápisy a bounded Query. Detail nepředstírá historický běh z updated_at.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
