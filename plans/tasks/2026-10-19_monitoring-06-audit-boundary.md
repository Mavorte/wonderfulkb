---
title: "Monitoring: zavést immutable Event a fail-open auditní rozhraní"
type: implementation
---

# Monitoring: zavést immutable Event a fail-open auditní rozhraní

## Goal
Business tok může předat allowlistovanou událost jedinému injektovanému listeneru bez vlivu selhání auditu na svou odpověď či stav.

## Files/functions
Nové `be-document-processing/src/document_processing/audit/{__init__,audit_events,audit_listener}.py`, `be-document-processing/tests/test_monitor_audit_boundary.py`; factory seam v `bootstrap.py`, bez připojování business hooků.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Implementovat 13 schválených Event typů a immutable envelope schema_version,event_id,case_id,document_id,sequence,type,occurred_at. FileReceived bez run_id, ostatní s ním. allowlist payload, bezpečný error code, jen známé měření; žádné recorded_at. RunQueued kontext pouze schválené známé hodnoty uloženého jobu a nezaměnitelná reference vstupu, nikoli aktuální prostředí. NoOp a skutečný fail-open listener izolují serializaci i sink výjimku v předem omezeném časovém rozpočtu. Žádná neomezená fronta/background vlákna.

## Boundaries
Žádná persistence, nové service/plugin registry, raw výjimky, celé job/config/result ani texty/hodnoty dokumentů. Žádný audit retry/outbox/replay. Neměnit business timeout/retry/lease. Nové moduly musí mít uvedená domain-qualified jména, ne events.py/listener.py/storage.py/utils.py.

## Verification
pytest `be-document-processing/tests/test_monitor_audit_boundary.py`: FileReceived/run validace, immutable payload a denylist soukromých polí, neznámá měření nejsou nula; NoOp, fungující, výjimku házející a deadline selhávající fake sink vrací stejné business sentinel výsledky. Doložit časové omezení bez úniku workerů. Syntax/protokol nesmí lákat business k importu boto3.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
