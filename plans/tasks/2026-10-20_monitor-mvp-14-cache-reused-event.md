---
title: "Monitoring MVP: událost skutečného použití stránkové cache"
type: implementation
---
# Monitoring MVP: událost skutečného použití stránkové cache

## Goal
Interní audit přijme a idempotentně uloží PageCacheReused jako důkaz předaného úspěšného načtení A validace uložené stránky, nikoli nového OCR. Malá event/store část slice 6.

## Files/functions
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`, existující fail-open auditní hranice podle potřeby; nový focused `be-document-processing/tests/test_monitor_cache_reused_events.py`. Proposal `proposal-20261019-150954-c8891f`, sections `slice-cache-reused`, `signals`, `instrumentation`; `plans/monitoring/mvp-reference-20261019.md` a event kontrakt `plans/tasks/2026-10-20_monitor-mvp-12-page-outcome-events.md`.

## Change / exact contract
- Pouze nový PageCacheReused: společná obálka, povinné skutečně předané run_id, kladný attempt_no a page_number, stage=page_transcription, stabilní producer-supplied event_id. Scope run/attempt je AKTUÁLNÍ použití cache, ne původ jejího obsahu. Nevytvářet execution identitu ani domnělou source_attempt/source_run.
- Povinný `cached_status` = completed/failed z validovaného Page.status; reuse není automaticky úspěšný OCR. Volitelné `cached_method` = native/vision a `cached_model` jsou údaje uloženého výsledku, nikoli důkaz volání v aktuálním pokusu nebo původní skutečné inference. Nebrat je z dnešního environmentu; chybějící model unknown/null. Zvláštní cached_* názvy brání záměně s provedenou cestou nového zpracování.
- Použít existující allowlist `artifact_ids` jen pro známou opaque referenci skutečně použitého uloženého výsledku; pokud není spolehlivě známá, vynechat a netvrdit dostupnost/historickou neměnnost. Nezakládat resolver nebo umělou referenci kvůli povinnému poli. Žádné bucket/key, URL, text/markdown/blocks/tables, dimensions, raw warning/error nebo celý Page. Cached failed stav nevyžaduje kopii chybového obsahu.
- Žádný PageCompleted/PageFailed ani StepStarted/StepFinished jako automatický vedlejší produkt reuse. Reuse není další nové zpracování stránky, cache miss ani pouhé HEAD nejsou tento event. Kontrakt přijímá explicitně předanou událost; sám cache nečte a nevyrábí události podle současného S3/business snapshotu.
- Zachovat immutable event_id idempotenci, document partition a occurred_at jako jediný uložený event timestamp. Nevyžadovat v deníku RunQueued/AttemptStarted nebo původní cache event. Business-facing auditní hranice zůstává best-effort/fail-open i při chybě validace/serializace/persistence; direct validator odmítá malformed input bez mutation.

## Boundaries
Pouze wonderfulkb. Žádný producer hook, změna cache klíčů/obsahů/retence, OCR nebo model call, queue/retry/lease/business schema/execution změna, outbox, index/projekce, content API či deployment/live replay. `be-document-processing/.../pipeline.py:85–87` je sémantická reference; checked-in DocumentWorker a `be-validator-agent/pipeline/run.py` nejsou důkaz totožného deployed produceru. Jen kontrakt/store, ne celý worker→HTTP slice. Nové soubory doménově kvalifikované; žádné events.py/state.py/utils.py.

## Verification
Implement the TDD cycle using skill:tdd. Focused fake/Moto: completed cache a failed cache roundtrip se stejným cached_status, unknown model/reference, duplicate bez změny/nového eventu, run/attempt/page izolace, missing run/invalid attempt/page/status/cached payload odmítnut bez zápisu; v úložišti pouze allowlist bez obsahu. Assert nedochází k výrobě nového OCR/Step terminálu ani k cache/model I/O. NoOp/failing audit boundary nemění caller výsledek; zachovat předchozí kontrakty a registrované gates. Hermetické příklady nejsou důkaz skutečné cache větve nebo live workeru.
