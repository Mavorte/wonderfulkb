---
title: "Monitoring: zaznamenat stránkové outcome bez duplicitních terminálů"
type: implementation
---

# Monitoring: zaznamenat stránkové outcome bez duplicitních terminálů

## Goal
Nová práce na stránce má jeden začátek a jeden pozorovaný PageCompleted/PageFailed, bez dvojího započítání konce.

## Files/functions
`be-document-processing/src/document_processing/pipeline.py` OCR větev a potřebné explicitní seam v `pdf_first.py`; nové `be-document-processing/tests/test_monitor_page_outcomes.py`; audit interface a source/cache hook.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Na cache miss StepStarted page_transcription se run/attempt/page; po pozorovaném outcome PageCompleted nebo PageFailed, nikoli navíc StepFinished/StepFailed pro stejný stránkový terminál. Skutečně doložená native/vision metoda, trvání celého kroku a bezpečný kód. Budget failure před OCR nesmí převzít vision z placeholderu jako skutečnou metodu nebo model call; unknown ponechat null. Reference artefaktu pouze při potvrzené dostupnosti. Cache reuse není nové OCR. UI projekce bude počítat stránku jen jednou.

## Boundaries
Bez text/blocks/tables, vymyšleného model usage/ceny a změn retry/cache/render/OCR pravidel. Nezachycený konec nepřemalovat na failed. Bez skutečné inference.

## Verification
pytest `be-document-processing/tests/test_monitor_page_outcomes.py`: native, vision, provider failure, worker budget před call, cache reuse, partial stránky a duplicate event. Assert přesný event count/correlation a žádný falešný call/metoda. NoOp/healthy/failing listener zachová stejné Page/business výsledky i provider call trace. Zachovat test_pdf_first a test_api_pipeline.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
