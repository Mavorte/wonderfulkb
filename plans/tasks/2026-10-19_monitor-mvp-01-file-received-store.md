---
title: "Monitoring MVP: uložit a přečíst jeden FileReceived event"
type: implementation
---
# Monitoring MVP: uložit a přečíst jeden FileReceived event

## Goal
Malý interní auditní store umí idempotentně uložit FileReceived a bounded dotazem přečíst události dokumentu.

## Files/functions
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`, `audit_queries.py` (žádné nové generické `events.py`, `storage.py`, `queries.py`), `be-document-processing/tests/test_monitor_audit_storage.py`; auditní resource/IAM pouze v existujících templates. Read-only MVP kontrakt: `plans/monitoring/mvp-reference-20261019.md`, sekce Minimum společné prvním taskům.

## Change
Jen obálka FileReceived: schema_version, event_id, case_id, document_id, sequence, type, occurred_at; bez run_id či business obsahu. Samostatná auditní tabulka `wonderfulkb-uw-document-processing-audit`, document partition a stabilní event identity pro conditional put. Repeat nemění uložený event. Malý write/read interface, Query s limit a scope-bound continuation; bez obecného event frameworku. Jen potřebná konfigurace a konečný SDK timeout; nekonfigurovaný store je explicitně vypnutý, nedostupné čtení je chyba.

## Boundaries
Pouze repo wonderfulkb.
Bez producer hooku, HTTP, deploy, run projekcí, revision/fencing, incremental refresh nebo TTL. Existující business tabulky a package API neměnit. occurred_at je jediný ukládaný timestamp. Nepřebírat širší acceptance starého tasku 7.

## Verification
Focused pytest s fake/Moto: put→read stejných ID, duplicate zůstane jeden event, druhý dokument oddělený, dvě stránky, read exception není empty success. Ověřit bounded Query místo Scanu. Stačí tyto scénáře a existující registrované gates; žádná plošná fault matice. Implement the TDD cycle using skill:tdd.

## Společné umístění API
Processing Monitor API je jediný router `be-intake/app/processing_monitor_routes.py` ve stávající službě `wonderfulkb-ingest` (Python/FastAPI, AWS App Runner, eu-central-1), na stejném hostu jako upload. Aktuální test host `https://vt9mavpjky.eu-central-1.awsapprunner.com` je provozní údaj, ne hardcoded default. První operace: `GET /v1/cases/{case_id}/processing/documents/{document_id}/events?limit=50`, pokračování parametrem `next_token`. JSON `items`, `next_token`, `observed_at`. Žádná nová služba, Lambda ani API Gateway; tento kontext nerozšiřuje deliverable tasku o HTTP nebo deployment tam, kde jsou vyloučené.
