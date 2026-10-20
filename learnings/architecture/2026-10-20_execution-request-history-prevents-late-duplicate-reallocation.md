---
title: "Pozdní duplicity enqueue vyžadují trvalé vazby všech request keys"
date: 2026-10-20
category: architecture
component: backend
tags: [wonderfulkb, monitoring, dynamodb, enqueue, generation]
file_type: decisions
---

Při plánování execution ledgeru pro be-validator-agent/trigger nestačí jediný STATE item s posledním enqueue_key: pozdní redelivery původního stream recordu po vytvoření druhé generace by mohla založit třetí. Zachovat trvalý immutable REQUEST#<enqueue_key> → run/generation item pro každý přijatý logický enqueue vedle STATE counter itemu. V jedné DynamoDB transakci podmíněně zapsat request mapping, aktualizovat STATE a provést business queued transition; při retry nejprve konzistentně číst mapping. Po pozdní duplicitě starého klíče neodesílat zprávu za novou generaci. Neodstraňovat vazby po dokončení generace, dokud mohou staré stream zprávy znovu dorazit. Při obnově po ambiguous commit se tím dá prokázat původní alokace bez syntetické identity. Plánovací artefakt musí začínat # Plan YYYY-MM-DD: ...; povolené ## nadpisy je nutné zkontrolovat zvlášť.