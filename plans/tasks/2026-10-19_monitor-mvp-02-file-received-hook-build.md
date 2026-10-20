---
title: "Monitoring MVP: FileReceived po potvrzeném uploadu"
type: implementation
---
# Monitoring MVP: FileReceived po potvrzeném uploadu

## Goal
Skutečný intake uloží jeden FileReceived pro každý nově potvrzený dokument. Porucha auditu nezmění výsledek uploadu.

## Files/functions
`be-intake/app/main.py`, `be-intake/app/Dockerfile`, potřebný existující build entrypoint a `be-intake/template.yaml`; jediný interní package `be-document-processing/src/document_processing/audit/`. Malý listener pojmenovat `audit_listener.py`, ne obecné `listener.py`/`utils.py`. Vstup: audit store `audit_storage.py`/`audit_queries.py` a `plans/monitoring/mvp-reference-20261019.md`.

## Change
Použít store pro FileReceived se stabilním event_id. V transakčním commit bodě main.py zachytit pouze řádky skutečně zapsané tímto požadavkem; emitovat až po úspěšném S3 + metadata commitu. Concurrent winner/duplicate ani neúspěšný commit nejsou nová událost. Case/document ID z potvrzeného řádku, occurred_at z přijetí, žádný run_id či obsah dokumentu.

Auditní hranice zachytí chybu tvorby, serializace i persistence; konečný timeout bez audit retry. Zachovat business návrat/chyby/writes. Propojit intake image se skutečně instalovaným interním package, bez duplikace jeho zdroje. Audit resource/IAM jen pro vlastní tabulku; neměnit business schéma. Doložit přesný build příkaz a import z výsledného artefaktu.

## Boundaries
Pouze repo wonderfulkb. Bez HTTP monitor endpointu, worker/queue změn, deploy nebo nového deployment frameworku. Žádný event bus/outbox, RunQueued nebo rozsáhlý refaktor intake.

## Verification
Focused test: nový upload→jeden event; duplicate→žádný další; failed metadata commit→žádný event; výjimka audit boundary→stejný úspěšný upload. Smoke import skutečného zabaleného package. Existující gates zachovat; žádná úplná matice timeoutů/chaosu. Implement the TDD cycle using skill:tdd.

## Handoff
Krátký `plans/monitoring/file-received-build-contract.md`: store interface, config názvy, build/import příkaz a event identity. Bez secrets. Source a lokální ověření nejsou nasazení.

## Společné umístění API
Processing Monitor API je jediný router `be-intake/app/processing_monitor_routes.py` ve stávající službě `wonderfulkb-ingest` (Python/FastAPI, AWS App Runner, eu-central-1), na stejném hostu jako upload. Aktuální test host `https://vt9mavpjky.eu-central-1.awsapprunner.com` je provozní údaj, ne hardcoded default. První operace: `GET /v1/cases/{case_id}/processing/documents/{document_id}/events?limit=50`, pokračování parametrem `next_token`. JSON `items`, `next_token`, `observed_at`. Žádná nová služba, Lambda ani API Gateway; tento kontext nerozšiřuje deliverable tasku o HTTP nebo deployment tam, kde jsou vyloučené.

## Povinné oddělení monitoringu od business implementace
Dodrž sekci `Společné architektonické a fail-open hranice` → `Izolace implementace` v `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md`. Jeden injektovaný listener přes malé rozhraní; jeho implementace, tvorba/validace/serializace událostí, auditní I/O a izolace chyb zůstávají v `be-document-processing/src/document_processing/audit/` (reuse `audit_listener.py`, případně `audit_instrumentation.py`). Business caller pouze předá explicitní minimální hodnoty na potvrzené sémantické hranici; composition root zapojí závislost. Žádné auditní boto3/storage DTO, catch/retry bloky, globální context ani kopírování mutable business objektů do business toku. Změna nemá zavádět novou funkci business kvůli auditu.
Ověřit směr importů a skutečného callera s NoOp, funkčním listenerem a selhávajícím sinkem: stejné business writes/pořadí, návrat/chyby a počet provider volání tam, kde relevantní. Zde uvedené požadavky nezvětšují event ani runtime scope tasku.
