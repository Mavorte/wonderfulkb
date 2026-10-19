---
title: "Globální Case Client listing používá samostatný Scan a cursor"
date: 2026-10-19
category: architecture
component: backend
tags: [case-client, dynamodb, pagination, api]
---

Globální GET /cases nesmí předávat None do klientsky vázaného listovacího helperu: ten nejprve čte klienta a používá GSI Query. Přidej explicitní `list_cases` port a vlastní tabulkový Scan nad cases, s cursor fingerprintem odděleným od client-scoped cesty. Při naplnění response limitu uprostřed SDK stránky musí cursor ukazovat na poslední vydaný case_id; token na LastEvaluatedKey by přeskočil zbytek této stránky. Zachovej veřejnou projekci v handleru a chraň nový GET stejným API-key mechanizmem.
