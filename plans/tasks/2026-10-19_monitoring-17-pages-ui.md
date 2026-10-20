---
title: "Monitoring: zobrazit stránky, historické výstupy a bezpečnou diagnostiku"
type: implementation
---

# Monitoring: zobrazit stránky, historické výstupy a bezpečnou diagnostiku

## Goal
Uživatel si pro konkrétní run/pokus otevře stránkové mezivýsledky a povolené artefakty bez záměny tehdejšího a dnešního obsahu.

## Files/functions
Nové `apps/backoffice/app/src/cases/ProcessingPages.tsx`, typovaný artifact klient a focused frontend testy; zapojení v `ProcessingMonitor.tsx`. Existující pages/artifacts API a autorizovaná content proxy.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Lazy záložky Stránky a mezivýsledky / Výstupy a diagnostika. Stránka ukazuje číslo, doloženou metodu, cache reuse, outcome a bezpečný error, preview/text/structured output pouze podle konkrétního artifact_id a permission. Paging, loading, pending, expired, unavailable a 503 nezaměnit. Scope run+attempt je explicitní; cache reuse není nový OCR call a unknown metoda není vision. Historická reference chybí→vysvětlená nedostupnost, nikoli dnešní preview. Diagnostika pouze schválené známé technické parametry; verze nejsou reprodukovatelnost.

## Boundaries
Žádné editace dokumentových hodnot/historie oprav v MVP, HTML/instrukce v přepisu nespouštět, raw provider payload a interní bucket/key nevystavovat. Žádné kopie business obsahů do auditních events a žádné inference kvůli náhledu.

## Verification
Use the visual-acceptance skill for visual verification. `pnpm -C apps/backoffice/app build` a focused testy: partial stránky, cache, nulové skutečné hodnoty vs unknown, chybějící historická verze, content 403 a error retry, změna run/attempt bez stale obsahu. Text `<script>` zůstane textem; široký/úzký layout a omezená role nesmí zobrazit content download.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
