---
title: "Step audit: stage allowlists a Moto roundtrip"
date: 2026-10-20
category: test-failures
component: backend
tags: [audit, pytest, moto, step-events]
file_type: rules
---

# Step audit pro další skutečně pozorované stage

Audit Step události používají uzavřené allowlisty `STEP_STAGES` a `STEP_ERROR_CODES` v `audit_events.py`. Přidání stage nepotřebuje nový event typ ani store dispatch, protože `AuditStore` persistuje existující Step třídy polymorfně. Moto `read_document` vrací dekódované event objekty v pořadí klíče úložiště, nikoli nutně pořadí `sequence`; roundtrip ověřujte podle `event.type` a pro dekodér předejte `event.to_item()`.

V tomto prostředí musí Python testů odpovídat projektu (3.9 neumí modelové union typy používané backendem) a mít dev závislosti. Izolovaný Python 3.14 venv s `requirements-dev.txt` umožnil focused a celou suite.
