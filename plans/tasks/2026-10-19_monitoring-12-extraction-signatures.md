---
title: "Monitoring: zachytit extraction a skutečný signature outcome"
type: implementation
---

# Monitoring: zachytit extraction a skutečný signature outcome

## Goal
Extrakce a zapnutý signature detector vytvářejí společné Step události s pravdivým outcome bez hodnot dokumentu.

## Files/functions
`be-document-processing/src/document_processing/{pipeline,signatures}.py` existující extraction a detect volání; nové `be-document-processing/tests/test_monitor_extraction_signatures.py`; auditní rozhraní.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Extrakci instrumentovat pouze pokud existuje neprázdný completed seznam stránek; StepStarted a pozorovaný StepFinished/StepFailed. Signature krok pouze při skutečně zapnutém detectoru, outcome ze statusu vrácené sekce: detect může vrátit failed bez vyhození výjimky. Úspěch s nulovým počtem nálezů není skipped/unknown. Bez podpisových hodnot/citací či extrahovaných polí, bezpečná délka/čas jen pokud známé. Signature config není uložený job.config; nevyrábět historický model/konfiguraci z aktuálního prostředí.

## Boundaries
Žádné změny OCR processing_status kvůli podpisovému kroku, extractor pravidel ani provider call počtu. Žádný nový detektor nebo model call. Dvě semanticky související Step instrumentace, žádná přestavba pipeline.

## Verification
pytest `be-document-processing/tests/test_monitor_extraction_signatures.py`: žádné completed stránky→žádná extraction; extraction success/error; detector off, completed s nulou nálezů, returned failed bez výjimky a hozená chyba. Zkontrolovat event payload bez business hodnot a zachování výsledku se všemi sink režimy. Zachovat test_extraction_validation a test_signatures.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
