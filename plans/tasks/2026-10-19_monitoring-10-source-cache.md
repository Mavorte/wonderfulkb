---
title: "Monitoring: zachytit ověření vstupu a skutečné cache reuse"
type: implementation
---

# Monitoring: zachytit ověření vstupu a skutečné cache reuse

## Goal
Časová osa rozliší jeden source_validation krok a skutečné reuse stránky, aniž by si vymýšlela model call.

## Files/functions
`be-document-processing/src/document_processing/pipeline.py` (`process`, config/version/hash/open a cache větev); nové `be-document-processing/tests/test_monitor_source_cache.py`; vstup audit listener/event API.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Jedno StepStarted před source validation, StepFinished po úspěšném otevření konkrétního zdroje, StepFailed při pozorované chybě. Žádný event pro každou vnitřní kontrolu. PageCacheReused až po úspěšném načtení a validaci cache stránky, se správným run/attempt/page a bezpečnou referencí, je-li doložená; cache miss není cache failure ani OCR call. Trvání měřit monotonic kolem skutečné oblasti; unknown není nula.

## Boundaries
Neměnit config/source validation, cesty ke cache/previews, znovupoužití cache nebo pořadí business operací. Bez auditních obsahů a doplňování historie. Neinstrumentovat preview jako novou neschválenou stage. Fail-open bez změny původních výjimek a lease.

## Verification
pytest `be-document-processing/tests/test_monitor_source_cache.py`: úspěch, config mismatch, špatný hash/verze, neotevřitelný PDF, validní/poškozená/chybějící cache; žádný fake model call u reuse. Gap po nezachyceném konci zůstává unknown. Se třemi sink režimy stejné business výsledky a počet provider/cache calls; zachovat test_pdf_first a test_api_pipeline.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
