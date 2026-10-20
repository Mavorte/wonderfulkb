---
title: "Monitoring: doložit publish, retry a terminály runů a pokusů"
type: implementation
---

# Monitoring: doložit publish, retry a terminály runů a pokusů

## Goal
ResultPublished/RetryEnqueued/AttemptFinished/RunFinished označují pouze skutečně dokončené hranice a zachovají business fencing.

## Files/functions
`be-document-processing/src/document_processing/pipeline.py` publikační a exception větve, enqueue seam v `service.py`/`bootstrap.py`; nové `be-document-processing/tests/test_monitor_publish_terminal.py`.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Step result_publishing zahrnuje celý současný publish postup, ne jen S3 put: validace resultu, write, job state a document state. ResultPublished až po potvrzené celé hranici. RetryEnqueued až po skutečném potvrzení zprávy, nikoli po změně status=queued. AttemptFinished patří ukončenému pokusu; RunFinished jen skutečnému terminálnímu běhu, ne při queued retry. Failed/partial/completed zachovat; ztráta lease nepovolí starému workeru publikovat terminální projekci přes nového. Neznámý konec zůstane mezerou. Artifact reference neslibuje neověřenou historickou neměnnost.

## Boundaries
Žádná změna pořadí business writes, kompenzace/rollback, lease/retry počtu ani replay. Auditní failure nesmí spouštět business retry. Žádný raw result/error nebo nové runtime uploady v testu.

## Verification
pytest `be-document-processing/tests/test_monitor_publish_terminal.py`: chyba každého publish kroku, S3 úspěch a metadata failure, queue failure, partial s retry/bez retry, max attempts, conflict/stale owner a duplicate event. Porovnat business writes/response/calls pro NoOp/healthy/failing sink; žádný falešný ResultPublished či RunFinished u requeue. Zachovat full test_api_pipeline a test_aws_storage.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
