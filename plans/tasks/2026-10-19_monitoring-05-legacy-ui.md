---
title: "Monitoring: zobrazit současné dokumenty a poctivý legacy detail"
type: implementation
---

# Monitoring: zobrazit současné dokumenty a poctivý legacy detail

## Goal
V CaseDetail zobrazit dostupný list/detail současných dokumentů, i když žádný audit nikdy nevznikl.

## Files/functions
`apps/backoffice/app/src/cases/CaseDetail.tsx`, nové `ProcessingMonitor.tsx` a typovaný `getProcessingDocuments.ts` vedle něj; focused frontend testy v této oblasti. API návrh a autorizované list/detail proxy jsou vstupní rozhraní.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Použít title→filename→ID, matched/upload_only/analysis_only/audit_only, paginaci i empty-page-with-token, aktuální analysis status a neznámé hodnoty. Záložky oddělí Dokument a analýzu od Průběhu/mezivýsledků. Legacy má explicitní unavailable/not_instrumented; ne vymyšlené runy z updated_at. Odlišit loading, skutečně prázdný list, 403/404 a 503. Souhrny celého case nepočítat z jedné stránky. Číst jen otevřenou oblast.

## Boundaries
Bez auditní instrumentace, polling enginu, nových runtime dat či předstírané historie. Nepřepisovat zbytek case formuláře. API credential zůstává mimo browser.

## Verification
Use the visual-acceptance skill for visual verification. Syntetické fixtures pro legacy, analysis-only, selhání zdroje a unknown status; žádná inference. `pnpm -C apps/backoffice/app build` a focused UI test musí doložit empty vs unavailable vs error, další stránku a zachování case UI. Vizuální kontrola širokého i úzkého layoutu a bezpečný text rendering.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
