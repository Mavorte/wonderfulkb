---
title: "Monitoring: emitovat FileReceived na potvrzeném ingest commitu"
type: implementation
---

# Monitoring: emitovat FileReceived na potvrzeném ingest commitu

## Goal
Jeden skutečně potvrzený příjem dokumentu může vytvořit document-scope FileReceived bez vymyšleného běhu.

## Files/functions
`be-intake/app/main.py`, jeho stávající composition/injection seam; kontrakt `plans/monitoring/producer-contract.md`, auditní rozhraní z interního package dokumentové služby. Nové `be-intake/tests/test_monitor_file_received.py`; jen nezbytné source/packaging propojení dle doloženého ingest routingu.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Hook až po skutečném S3 a metadata commit současného intake, se skutečnými case_id/document_id a occurred_at. Spotřebovat konkrétní schválený routing/injection z producer kontraktu; pokud neexistuje použitelný přístup k internímu listeneru ve stávajícím deploymentu, doložit přesný chybějící interface, nenahradit jej kopírovanou audit implementací nebo novou službou. Opakované potvrzení téhož příjmu idempotentní podle kontraktu. Nikdy run_id. Emitovat po úspěchu, ne při presign či zahájení přenosu.

## Boundaries
Žádný upload progress, nový run, změna ingestion identity/statusu nebo auditní kopie souboru/metadat. Fail-open nesmí měnit HTTP/commit ani rollbackovat business. Žádné nové broad cloud oprávnění, nasazení nebo skutečný upload v worker testu.

## Verification
pytest `be-intake/tests/test_monitor_file_received.py` se stuby S3/metadata/listener: před commit žádný event, selhání každé části žádný falešný FileReceived, úspěch se správnou identitou, opakování bez duplicit, audit vypnutý/výjimka/deadline zachová původní response a zápisy. Porovnat request/commit traces s baseline.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
