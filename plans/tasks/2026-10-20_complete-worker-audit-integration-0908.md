---
title: "Monitoring worker: dokončit skutečná producer volání a behaviorální důkaz"
type: implementation
---
# Dokončit skutečné auditní producer hranice

Původnífc4580ab dodal pouze mapu unsupported hranic a test dokumentace, žádnou skutečnou instrumentaci. Chybí technický executioncontext: process_document nedostává authoritative attempt identity, claim je status string, enqueue result se zahazuje. Zachovat worker-instrumentation-contract.md i celý původní failed checkpoint/proof; nepovažuj další blocker dokument za funkční výstup. Existující scope nedovoluje změnit execution model nebo vyrobit fakeidentitu.

## Doložený nedodělek
Po skutečném dostupném executioncontext rozhraní minimálně zapojit skutečné doložené callery přes jediný injektovaný fail-open listener z audit package. Dodat skutečnou podporovanou stage/event/caller mapu, ne deklarovat všeunsupported za kompletní instrumentaci. Přesná source/NoOp/functioning/failing equivalence, business write order/return/errors/providercount a buildimport proof musí testovat volajícího, nikoli grep kontraktního Markdown. Stage, které canonical worker vůbec nemá, zůstávají unsupported bez nového business kroku.

Designovaný projektový be-document-processing/.venv/bin/python (moderníPython), správný workerpackagecwd/PYTHONPATH; žádný systémový3.9 fallback. pytest,pypdf a další deklarované dependencies ověř před capture. Starý RED na chybějící pypdf není behavioralRED, nepřebarvuj ho. Nový vlastní taskID skutečnýRED→GREEN stejnáargv přes povolené skill:tdd rozhraní; zachovat historii a registrované gates. Nebypassovat permissions nebo měnit execution/auth/config/instructions/frameworky. Žádné deploy/live/model/replay.

## Původní přesný scope a bezpečnostní hranice
# Monitoring MVP: napojení skutečných worker hranic na audit

## Goal
Zavést auditní producer volání do skutečných doložených worker hranic pro sections4–10, nikoli pouze synthetic event store. Proposal `proposal-20261019-150954-c8891f`, `slice-retry-terminal`. Současně popsat přesné supported/unsupported stage capabilities; žádný druhý worker.

## Files / technical inputs
Canonical source/build/context kontrakt `plans/monitoring/runtime-producer-context-contract.md` a immutable execution context předávaný skutečným queue/claim callerem. Skutečný checked-in pipeline owner `be-validator-agent/pipeline/run.py`, případné reálné volající a audit package v `be-document-processing/src/document_processing/audit/`. Event/task kontrakty10–24 a `plans/monitoring/next-slices-source-seams-20261019.md`. Starý `be-document-processing/.../pipeline.py` a signatures.py slouží jen sémantické referenci, ne důkazu deployed ownera. Chybějící skutečný context/producer/build/Stage counterpart je konkrétní TECHNICKÝ blocker, nesmí být nahrazen fake/no-op nebo novým execution modelem.

## Required work
- Reuse existující fail-open audit boundary s konečným timeoutem a no audit retry; explicitní context až do page/extraction/signature/publish/retry hranic, bez globals a bez copy business data. Instrumentovat skutečné callers, ne helper bez volajícího. Základní enabled/NoOp chování ekvivalentní.
- Source_validation jeden Step start/finish/failure podle skutečného ověření/open. Page: nová práce StepStarted + jediný PageCompleted/PageFailed, před-call budget není vision call; cache až validovaný skutečně použitý výsledek→PageCacheReused, žádný nový OCR nebo duplicitní Step terminál. Method/model/duration pouze doložené, cached metadata označené jako cached.
- Extraction jen skutečný neprázdný completed vstup, returned valid empty result není chyba. Signature jen enabled detector, rozlišit returned-failed/raised-failed/completed-empty, bez vlivu na OCR status. Neexistující stage ve skutečné cestě se nepřidává jako nový business krok kvůli auditu ani se neemituje jako success.
- Publish: Step a ResultPublished jen po skutečné celé potvrzené publish hranici, nikoli S3-only/partial writes. Nezměnit pořadí/rollback/owned writes; žádné zavedení fencing pokud ho canonical worker nemá. Partial publication nerovná se konec runu.
- RetryEnqueued až confirmed enqueue, AttemptFinished/RunFinished pouze známé skutečné konce s autoritativním contextem. Failed claim/lease lost/Conflict/ticho žádný smyšlený terminal. Max-attempt větev bez claimu nesmí dostat nový AttemptStarted. Absenci historii nedoplňovat.
- Source/build support/capabilities bezpečně doložit do `plans/monitoring/worker-instrumentation-contract.md`: actual symbol/caller/event/payload/test map, nepodporované hranice a důvod, build inclusion audit package. Capability neodvozovat zpětně pro legacy run z dnešního environmentu. Neznámá semantic mapping nesmí být slita s odlišnou stage.

## Boundaries
Pouze wonderfulkb; žádné změny business/execution identity/claim/lease/retry/queue/cache keys/provider count/detector rules, outbox, replay/reprocess nebo content API. Bez cloud/model call/live message/service/deploy, žádný přechod na jinou source větev. Žádné task lifecycle/instruction změny. Packaging jen existující worker artifact, ne nová služba. Nové doménové moduly `processing_audit_observations.py` jen pokud nutné, ne events.py/state.py/utils.py.

## Verification
Implement the TDD cycle using skill:tdd. Focused actual-caller fake tests NoOp vs failing sink zachovají business writes/order/errors/model-call count pro supported boundaries: cache completed/failed/corrupt miss, native/vision/pre-call-budget, extractor success/error/empty input, signature returned/raised/disabled, každý publish failure point a stale-owner jen pokud existující canonical semantics, confirmed/failed retry a max-attempt. Vyjmenovat unsupported skutečné branches, ne green syntetickou náhražku. Registered gates+hermetický build import ze skutečného worker entrypointu. Zdrojové/hooks důkazy nejsou deployed worker→HTTP smoke.

## Povinné oddělení monitoringu od business implementace
Dodrž sekci `Společné architektonické a fail-open hranice` → `Izolace implementace` v `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md`. Jeden injektovaný listener přes malé rozhraní; jeho implementace, tvorba/validace/serializace událostí, auditní I/O a izolace chyb zůstávají v `be-document-processing/src/document_processing/audit/` (reuse `audit_listener.py`, případně `audit_instrumentation.py`). Business caller pouze předá explicitní minimální hodnoty na potvrzené sémantické hranici; composition root zapojí závislost. Žádné auditní boto3/storage DTO, catch/retry bloky, globální context ani kopírování mutable business objektů do business toku. Změna nemá zavádět novou funkci business kvůli auditu.
Ověřit směr importů a skutečného callera s NoOp, funkčním listenerem a selhávajícím sinkem: stejné business writes/pořadí, návrat/chyby a počet provider volání tam, kde relevantní. Zde uvedené požadavky nezvětšují event ani runtime scope tasku.
