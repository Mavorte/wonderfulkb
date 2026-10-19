---
title: "Case Client: oddělit hotový backend od nových live integračních nástrojů"
date: 2026-10-19
category: architecture
component: backend
tags: [case-client, planning, deployment, integration, evidence]
file_type: rules
---

# Case Client: plánovat integrační nástroje kolem hotového backendu

Průzkum pro task-beca6825-147b-43d9-9fb6-694368e70948 dne 2026-10-19 našel hotový Python UUIDv4/201 kontrakt, strong GetItem, Decimal metadata a podmíněnou DynamoDB transakci, ale žádný komponentový deploy nástroj ani HTTP integration runner. README stále označovalo cloudovou fázi jako budoucí; to není důkaz aktuálního runtime v AWS.

Při navazující implementaci oddělit nové guardy deploy/HTTP nástrojů od existujícího backendu: focused RED má dokazovat chybu chování guardu, nikoli chybějící SDK/import nebo opakování historické UUID implementace. Nasazení dokazovat shodou lokálního Linux ZIP SHA256 s Lambda CodeSha256 a runtime/config readbackem před i po HTTP scénářích; hlavička backendu sama nestačí.

Budget syntetických klientů/cases a deploy pokusů vést task-wide v ledgeru, nikoli resetovat při opravě nebo redeployi. U ne-idempotentního POST nejistý timeout není oprávnění k retry; scoped run_id kontrola a případný BLOCKED musí zachovat pravdivost důkazu.

Tento poznatek pochází pouze z plánování a lokálního čtení souborů. Žádný deploy, cloudový readback ani live test v této session neproběhl.
