---
title: "Monitoring MVP: RunQueued v existujícím event deníku"
type: implementation
---
# Monitoring MVP: RunQueued v existujícím event deníku

## Goal
Interní auditní write/read rozhraní přijme idempotentní RunQueued se skutečnou předanou run identitou a vrátí jej ve stávajících dokumentových events.
## Files/functions
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`, `audit_queries.py`; nový focused test `be-document-processing/tests/test_monitor_run_queued.py`. Reference `plans/monitoring/mvp-reference-20261019.md`, sekce Rozšíření sekcí 2 a 3.
## Change
Přidat jediný typ RunQueued: společná obálka + povinný opaque run_id. Caller musí dodat skutečnou stabilní identitu, žádný default UUID ani odvození z dokumentu/času/SQS receive count. Neprázdné známé schválené run_context hodnoty mohou být předané jako whitelist, chybějící zůstanou unknown; nečíst dnešní worker environment ani ukládat celý job/config. Existující conditional event_id idempotence, occurred_at jediný timestamp a bounded document Query zůstávají. Stávající FileReceived bez runu musí fungovat.
## Boundaries
Pouze wonderfulkb; žádný producer hook, queue/payload/business schéma, run index/projekce, nový runtime nebo AWS deployment. Toto je kontrakt/store část, ne potvrzení live enqueue. Source/schema starého tasku09 je pouze sémantická reference, ne živý owner.
## Verification
Focused pytest: FileReceived + RunQueued read roundtrip, duplicate bez další události, chybějící run_id odmítnut bez mutation, context whitelist. Fake/Moto, žádný cloud. Zachovat registrované gates. Implement the TDD cycle using skill:tdd.
