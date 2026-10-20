---
title: "Monitoring: zachytit skutečné enqueue a začátek pokusu"
type: implementation
---

# Monitoring: zachytit skutečné enqueue a začátek pokusu

## Goal
RunQueued a AttemptStarted odpovídají skutečnému enqueue a úspěšnému claimu, nikoli přání aplikace.

## Files/functions
`be-document-processing/src/document_processing/{service,bootstrap,pipeline}.py` a auditní rozhraní; nové `be-document-processing/tests/test_monitor_queue_attempt.py`. Hook producer vazba dle `plans/monitoring/producer-contract.md`.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
RunQueued až po potvrzeném skutečném zařazení zprávy; výchozí lokální enqueue je dnes no-op, jeho úspěšný návrat není důkaz enqueue. Explicitně modelovat tento rozdíl v composition seam bez změny business výsledku. Pouze jednou uložený job.config a reference skutečného vstupu jako schválený run_context. AttemptStarted až po úspěšné claim aktualizaci/inkrementu attempts, se stejným run a skutečným attempt_no. Conflict, leased, hotový job a max-attempt bez claimu nejsou nový pokus. Kontext nesbírat z aktuálního worker prostředí.

## Boundaries
Bez nových business retry/lease mechanismů, identity jobu nebo auditního outboxu. Neřešit terminální události ani jiné hooky. Zachovat lokální zpracování i AWS queue chování; žádná skutečná SQS/inference.

## Verification
pytest `be-document-processing/tests/test_monitor_queue_attempt.py`: no-op vs potvrzené enqueue, queue výjimka, opakování/duplicate, claim conflict/lease, číslo pokusu, job snapshot vs změněné prostředí. Maticí NoOp/healthy/failing sink prokázat stejné responses, repo mutations a enqueue calls. U deklarovaných verzí netvrdit obsahový hash.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
