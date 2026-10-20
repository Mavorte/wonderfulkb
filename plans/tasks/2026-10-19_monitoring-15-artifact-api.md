---
title: "Monitoring: bezpečně zpřístupnit jen doložené artefakty a jejich verze"
type: implementation
---

# Monitoring: bezpečně zpřístupnit jen doložené artefakty a jejich verze

## Goal
Autorizovaný čtenář získá konkrétní historický obsah pouze podle doložené nezaměnitelné reference; nedostupnost se nevydává za dnešní výsledek.

## Files/functions
Nové `be-document-processing/src/document_processing/audit/audit_artifacts.py`, `be-document-processing/tests/test_monitor_artifacts.py`; doplnit artifacts cesty v `processing_monitor_routes.py` a serverové backoffice proxy. Read-only blobs/source verze a journal access/producer kontrakt.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
List artefaktů podle document a volitelného run má paginaci; opaque artifact_id resolve pouze serverem, ověřit case/document/run scope, samostatné content oprávnění, původ a verzi objektu. Pending/expired/unavailable/confirmed absence rozlišit podle OAS. Document/page preview cesta sama nedokládá historickou neměnnost; bez důkazu obsah tehdejšího běhu nedostupný. Známý hash není záruka stažitelnosti/retence. Obsah se neukládá do deníku, žádné nové business manifesty.

## Boundaries
Neměnit S3 business klíče/lifecycle a nekopírovat originály/text/results. Žádné otevřené bucket/key, credential/URL logy či trvalé veřejné URL. Zachovat private,no-store, krátkodobé autorizované čtení, redakci chyb a bezpečný content-type.

## Verification
pytest `be-document-processing/tests/test_monitor_artifacts.py` přes fake/Moto: správná verze, zaměněný case/run, scope forgery, missing content permission, pending/deleted/verze chybí, přepsaný preview a současný result jiné run. Assert unavailable místo falešného fallbacku, žádné auditní business kopie, žádné write calls. Proxy test nepropustí credentials.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
