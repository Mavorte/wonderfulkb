---
title: "Přesná validace observation event DTO"
date: 2026-10-20
category: test-failures
component: backend
tags: [openapi, monitoring, json-schema, tdd]
---

# Přesná validace observation event DTO

OpenAPI parse a `$ref` resolution nestačí k ověření veřejného event kontraktu. Při změně observation DTO validuj celý OpenAPI dokument offline a zároveň testuj povinná scope pole, zakázaná pole a validní/nevalidní payloady přes JSON Schema validator.

Kontrakt je třeba odvozovat z event briefů, nikoli z interní obálky nebo generického názvu jako `outcome`. Například `AttemptFinished` vyžaduje `run_id`, `attempt_no` a enum `attempt_status`; `RunFinished` vyžaduje `run_id` a enum `run_status`, ale může vynechat `attempt_no`. `FileReceived` nesmí získat run scope.

Používej stejnou focused pytest argv pro skutečné RED a GREEN capture; accepted proof odlišuje selhání sémantické assertion od YAML/dependency/import problémů. Celá package suite může zároveň obsahovat nesouvisející reducer failures, které je nutné vykázat samostatně.
