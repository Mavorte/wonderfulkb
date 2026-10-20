---
title: "Audit DynamoDB: integrální Decimal při čtení striktní obálky"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, dynamodb, decimal, validation]
file_type: rules
---

# Audit DynamoDB: validace integer obálky po skutečném round-trip

Interní FileReceived dataclass odmítá bool a neinteger sequence/schema_version. DynamoDB resource však při čtení vrací čísla jako Decimal, takže přímé předání raw itemu do striktního konstruktoru nestačí. `FileReceived.from_item` v `be-document-processing/src/document_processing/audit/audit_events.py` převádí pouze integrální Decimal na int a používá explicitní sedmipolový allowlist; neintegrální čísla neprojdou validací. Technické pk/sk nepatří do veřejné obálky.

Ověřeno taskem task-4651db4a-86e4-4bd9-ad5d-09532bd16490: Moto put/read, duplicate se změněnou sequence i occurred_at, oddělení dokumentů a stránkování prošly; focused sada má 30 passing testů, celá Python sada 84. Jde o lokální adapter důkaz, nikoli deployed persistence. Při navazujících event typech zachovat explicitní převod a test skutečného resource round-trip, ne pouze fake dict s Python int.
