---
title: "Monitoring deploy: platné AWS přihlášení neznamená připravené auditní zdroje"
date: 2026-10-20
category: runtime-errors
component: backend
tags: [monitoring, aws, apprunner, audit, deployment]
---

Při steps HTTP implementaci task-252c7fcd fungovaly podepsané AWS MCP reads ve správném účtu a regionu a App Runner wonderfulkb-ingest byl RUNNING. DescribeService ale neměl AUDIT_TABLE_NAME ani monitoring auth ARN, ListTables neobsahoval auditní tabulku, ListSecrets neobsahoval monitoring policy a instance role neměla příslušné resource grants. Lokální wheel/image a HTTP testy tyto chybějící závislosti nemohou napravit. Před image-only rolloutem ověřit skutečné runtime bindings, existenci zdrojů, minimální IAM a bezpečnou syntetickou fixture. Bez nich zachovat nulové writes a explicitní DEPLOYED/LIVE neověřeno; neoznačovat stav jako credential denial a nevymýšlet provisioning budget. Konkrétní evidence a same-task operator krok jsou v plans/monitoring/task-252c7fcd-6de4-4406-813b-e7771d61da74-runtime-evidence.md. Při souběžných změnách navíc porovnat source hashes po image build: jiný writer opakovaně rozšířil source-validation-only steps o pages a změnil assertions. Nový green širších testů není důkaz souladu s původním plánem ani provenance již sestaveného image; zastavit overwrite race a sjednotit vlastnictví před novým buildem a deploymentem.