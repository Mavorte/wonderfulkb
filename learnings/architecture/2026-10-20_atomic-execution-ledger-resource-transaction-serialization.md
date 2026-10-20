---
title: "Atomický execution ledger a boto3 resource transakce"
date: 2026-10-20
category: architecture
component: backend
tags: [dynamodb, trigger, execution, transactions, audit]
---

# Atomický ledger pro run a claim musí sdílet transakci s business podmínkou

V triggeru `be-validator-agent/trigger/processing_execution_claims.py` je business analysis row nadále vlastníkem `queued`/`processing`/930s lease, ale `run_id`, `generation` a `attempt_no` jsou v samostatné tabulce. Enqueue transakčně provede původní podmíněný business zápis, CAS `STATE` a neměnný `REQUEST#<hash(request_key)>`. Retry po ztracené odpovědi načte request mapping konzistentně, takže nevygeneruje novou generaci; stejné platí po vytvoření dalšího runu. Claim transakčně mění business status a CAS zvyšuje attempt counter; token readback po nejednoznačné odpovědi chrání před dvojím započítáním. Platná lease a terminal status neinkrementují counter.

Specifikum boto3: `resource.meta.client.transact_write_items` používá resource serializer. Předání ručně vytvořených DynamoDB AttributeValues (`{"S": ...}`) způsobilo dvojí serializaci na mapy a Moto vrátilo `TransactionCanceledException` s `TypeError` pro každou akci. Předávat běžné Python dict hodnoty; `TypeSerializer` použít jen s nezávislým nízkoúrovňovým clientem. Při reprodukci kontrolovat `CancellationReasons` a skutečný vstup do `TransactWriteItems`, ne považovat tento infrastrukturní fail za TDD RED.

V2 zpráva obsahuje owner-issued `run_id`/`generation`; stará v1 zpráva se nesmí spojit s novou generací. V1 lze jednorázově bindovat jen pro existující před-upgrade queued/processing řádek, a to pod podmínkou aktuálního business stavu. Warm `Options` zůstává bez identity; immutable `ExecutionContext` se posílá explicitně do `pipeline.run_document`. Audit listener persistuje RunQueued jen po potvrzeném SQS `MessageId` a AttemptStarted jen po transakčně potvrzeném claimu; outage auditu nemění business write.

Při build provenance nestačí úspěšný Docker build a staged importy: image-internal import smoke může selhat již při rozbalování image (`no space left on device`). Tento stav je inconclusive, ne installed/deployed green; před dalším pokusem musí vlastník Docker disku zajistit kapacitu bez nevyžádaného mazání cizích build cache.
