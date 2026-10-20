---
title: "Monitoring worker: claim identity není potvrzení retry a fail-open patří i calleru"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, worker, retry, execution-context, fail-open, planning]
file_type: rules
---

# Monitoring worker: claim identity neprokazuje potvrzené retry

Při plánování 20. 10. 2026 už `be-validator-agent/trigger/processing_execution_context.py` a `processing_execution_claims.py` dodávaly immutable execution context, stable generation a atomic claim ordinal. `common.py` již volal RunQueued po confirmed send a AttemptStarted po claimu; staré producer blocker dokumenty tento source stav nezachycovaly.

Tento posun sám nedokládá RetryEnqueued. `worker_handler._remember` vrací business řádek do queued a handler vrací batchItemFailures, ale obojí předchází SQS-managed redelivery a není potvrzením enqueue. `common.queue_case` posílá downstream case zprávu, nikoli retry dokumentu. Pro retry producer vyžadovat skutečný potvrzený owner boundary; při jeho absenci zapsat přesný interface blocker bez změny retry mechanismu nebo identity odvozené z ApproximateReceiveCount.

Samostatně otestovat throwing injected listener: standardní audit listener může izolovat sink chyby, zatímco přímé caller volání listener metody po business commitu stále může změnit návratovou hodnotu na exception. Behavioral test musí porovnat committed claim/result a business pořadí s NoOp variantou; signature assertion tuto vlastnost neprokazuje.

Zjištění pochází z inspection source při plánování task-b0db5177-2f43-4036-b080-af1ca7d143d5; neprokazuje instalaci, deployment ani live producer.
