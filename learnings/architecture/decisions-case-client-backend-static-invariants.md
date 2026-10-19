---
title: "Case & Client: statické mock invarianty při přidání DB adaptéru"
date: 2026-10-19
category: architecture
component: backend
tags: [case-client, dynamodb, mock, planning, tests]
file_type: decisions
---

Při plánování DynamoDB adaptéru pro be-case-client byl v tests/test_case_client_lambda.py nalezen AST test zakazující boto3/botocore ve všech src modulech; tests/test_case_client_template.py současně vyžaduje nepodmíněně jednu logs-only policy a doslovné mock env. Tyto kontroly patří první mock fázi a bez cílené aktualizace by legitimní DB adaptér nemohl projít. Zachovat všechny mock behavior testy, ale statický SDK zákaz omezit na mock/shared moduly a přidat přímý důkaz, že mock factory neinicializuje SDK ani credential chain. SAM testy vyhodnotí obě podmíněné větve: mock stále nemá aktivní DB práva, DB má pouze přesné table/index akce. Neodstraňovat plošně bezpečnostní testy kvůli novému backendu. Rozhodnutí vychází z plánování task-11fe7375-3c4e-4afe-b11b-cab49fc2c973; implementace, RED/GREEN ani cloudový běh v této session neproběhly.