---
title: "Monitoring MVP: skutečný runtime kontext a queue claim producer"
type: implementation
---
# Monitoring MVP: skutečný runtime kontext a queue claim producer

## Goal
Uzavřít zdrojovou integraci runtime→audit pro RunQueued/AttemptStarted a explicitní context předávaný workerem, bez změny business execution sémantiky. Proposal `proposal-20261019-150954-c8891f`, `slice-attempt-started`; doplňuje producer mezeru kontraktových sections2/3. Není samostatný discovery nebo souhlas s novým schedulerem/outboxem.

## Technical inputs / real limitation
Reference `plans/monitoring/live-trigger-evidence-20261019.md`, `next-slices-source-seams-20261019.md`, `mvp-reference-20261019.md`; runtime trigger source candidate475deafc567366c2587ef4d73fbf9a31fadb59f8 (read-only source inspection), `be-validator-agent/pipeline/run.py:run_document/Options`. Audit RunQueued/AttemptStarted kontrakt vyžaduje skutečnou run/attempt identitu, kterou audit nevyrábí. Zkoumaný trigger má make_message(v,type,case_id,document_id,force), Context.send bez response a claim queued/expired-processing bez run/attempt counter. Byte shoda2trigger modulů není provenance celého deployed image. Design runtime tabulky/outboxu ve source reportu je NESCHVÁLENÁ inference a obsahuje možné identity fencing; není implementační zadání.

## Required work / allowed implementation
- Reviewed plan musí jmenovat skutečný canonical producer/build caller, rozhraní confirmed enqueue a authoritative claim+attempt, souběhovou atomicitu a crash/ambiguous send semantiku na základě doloženého zdroje. Nepřipojovat starý DocumentWorker místo živé větve. Žádný checkout/fetch/source replacement nebo vytváření zmizelého triggeru z historického commitu jako live owner.
- Pokud už existuje skutečné autoritativní run/attempt rozhraní slučitelné s hranicemi níže, použít je, context předat explicitním immutable argumentem až do `run_document/Options` a dále, bez warm-global/environment identity. RunQueued až po potvrzeném úspěšném enqueue; AttemptStarted jen po skutečném úspěšném claim+attempt inkrementu. Duplicitní/unclaimed delivery neemitovat. Event_id stabilní pro tutéž doloženou událost; audit fail-open včetně tvorby/serializace.
- Pokud potřebné execution rozhraní neexistuje nebo nelze zachovat business kontrakt, je to TECHNICKÝ BLOKER, ne důvod vymyslet identity nebo dodat no-op adapter jako hotovou integraci. Zapsat přesnou chybějící interface/atomicity rozhodnutí a nejmenší navržený kontrakt do `plans/monitoring/runtime-producer-context-contract.md`; plán musí jasně oddělit požadovanou změnu execution od už schváleného auditu. Bez schváleného interface neimplementovat spekulativní counter/runtime tabulku/outbox. Nesmí označit zdrojovou integraci za dokončenou.

## Boundaries
Pouze wonderfulkb. Zachovat business tabulky/schéma, queue/retry/DLQ/lease930s a claim sémantiku; žádný implicitní nový fencing/supersession, outbox/recovery/replay/reprocess endpoint, auditní identita nebo ApproximateReceiveCount jako attempt. Žádný cloud/model/live message/deploy/service/scheduler zásah. Host vlastní instalaci/deploy a live smoke, source test není deployed proof. Neměnit task lifecycle nebo instrukce. Nové moduly doménově kvalifikované (`processing_execution_context.py` jen je-li nutný), ne state.py/common.py/utils.py.

## Verification
Implement the TDD cycle using skill:tdd. Hermetické testy skutečných callerů: concurrent/duplicate enqueue a claim, confirmed vs ambiguous send, žádný nový attempt na failed claim, dvě contexts bez leakage; failed audit zachová původní chování. Žádný no-op/mock-only adapter vydávaný za actual caller proof. Plný registered gates. Evidence source/build identity a explicitní unavailable blockers, bez soukromého obsahu. Bez autoritativních identit žádná falešná E2E success.

## Povinné oddělení monitoringu od business implementace
Dodrž sekci `Společné architektonické a fail-open hranice` → `Izolace implementace` v `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md`. Jeden injektovaný listener přes malé rozhraní; jeho implementace, tvorba/validace/serializace událostí, auditní I/O a izolace chyb zůstávají v `be-document-processing/src/document_processing/audit/` (reuse `audit_listener.py`, případně `audit_instrumentation.py`). Business caller pouze předá explicitní minimální hodnoty na potvrzené sémantické hranici; composition root zapojí závislost. Žádné auditní boto3/storage DTO, catch/retry bloky, globální context ani kopírování mutable business objektů do business toku. Změna nemá zavádět novou funkci business kvůli auditu.
Ověřit směr importů a skutečného callera s NoOp, funkčním listenerem a selhávajícím sinkem: stejné business writes/pořadí, návrat/chyby a počet provider volání tam, kde relevantní. Zde uvedené požadavky nezvětšují event ani runtime scope tasku.
