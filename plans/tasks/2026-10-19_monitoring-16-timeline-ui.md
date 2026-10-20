---
title: "Monitoring: zobrazit run timeline s řízeným pollingem"
type: implementation
---

# Monitoring: zobrazit run timeline s řízeným pollingem

## Goal
Průběh nabídne výběr běhu a pokusu, kroky i dokumentové události, a správně zastaví/obnoví polling.

## Files/functions
`apps/backoffice/app/src/cases/ProcessingMonitor.tsx`, nové `ProcessingTimeline.tsx`, typovaný history klient a focused frontend testy; bezpečné history proxy a kontrakt `plans/monitoring/journal-access-contract.md`.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Lazy load Průběh, oddělený document journal s FileReceived a filtrovaná run timeline. Přiznat partial/gaps/not_instrumented/unknown a neznámý nový stav. Poll 2–5 s jen viditelný aktivní audit, background pomaleji, Retry-After/backoff na 429/chyby, stop po terminal/nenakonfigurovaném auditu, ruční refresh vždy. Refresh přesně dle late-event cursor kontraktu i po terminal; opožděný event nesmí být trvale skryt. Starší odpověď/revision nepřepíše novější v témže scope; změna dokument/run/attempt ruší staré requesty.

## Boundaries
Žádné SSE/WebSocket, nekonečné legacy polling, odhad runu z updated_at ani směšování business status a auditu. Nezobrazovat serverové secrets, nulové neznámé metriky nebo souhrnnou cenu. Stránkové obsahy patří samostatné oblasti.

## Verification
Use the visual-acceptance skill for visual verification. `pnpm -C apps/backoffice/app build` a focused testy s fake clock/requests: visible/background, terminal/manual, 429 Retry-After, out-of-order odpovědi, změna scope, late insert, unavailable vs empty vs 503, FileReceived bez runu. Syntetická timeline na širokém/úzkém layoutu, bez skutečné inference.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
