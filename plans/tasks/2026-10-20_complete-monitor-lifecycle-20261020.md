---
title: "Monitoring lifecycle: dokončit pure reducer a úplnou testovací matici"
type: implementation
---
# Monitoring lifecycle: dokončit pure reducer a úplnou testovací matici

## Cíl dokončení
Nový samostatný implementační řez dokončuje nedodaný rozsah původního tasku task-1e8311a4-08b0-4142-9bf9-6553815e572e. Původní neúplné výsledky/proof zůstávají historické; nepřepisuj je a netvrď, že prošly. Referenční host review: plans/checkpoints/task-1e8311a4-08b0-4142-9bf9-6553815e572e.host-review.md.

Implementuj chybějící audit_lifecycle_observations.py a doplň existující focused test. Host znovu ověřil collection ImportError, ne hotovou implementaci. Doplň všechna chování původního briefu: orphan/terminal-only attempts, více runs/attempts, dedupe identity, reordered/late fragments, konfliktní terminals unknown/ambiguous, explicitní evidence/result scope, availability not_configured/not_instrumented/unknown/read failure. Token beze změny, vždy partial, žádné I/O ani absolutní latest inference. Zachovej přesné vlastnictví původního tasku.

## Skutečné lokální ověření a TDD
Použij již funkční projektový interpreter `be-document-processing/.venv/bin/python` z kořene repozitáře. Ověř importy/dependency před proof capture. Z kořene repo zvol focused argv `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/` + příslušný focused test filename; RED a GREEN přesně stejné argv, proof pod vlastním přiděleným task ID v kořenovém plans/checkpoints/. Chybějící interpreter/dependency/conftest import není genuine RED. Zachovej staré artefakty a nepoužívej staré task ID k obcházení odmítnutého proof cyklu. TDD helper použij pouze prostřednictvím načtené skill:tdd a jejích skutečně povolených rozhraní, ne grep čtení externích helper internals. Při odmítnutí oprávnění nic neobcházej; uveď konkrétní capability blocker.
Focused kontroly plus plné existující registrované gates (`npm --prefix apps/backoffice test` a `npm --prefix apps/backoffice run build`) a relevantní package pytest. Neignoruj cizí neúplné tests, nevylučuj je z full gate, nezmírňuj assertions; případnou nesouvisející collection chybu přesně odliš od výsledku vlastního focused testu. Pro runtime caller testy lze stejným projektovým Python spouštět konkrétní be-validator-agent/trigger/tests, všechny AWS dependencies musí být Moto/fixtures, ne live.

## Hranice
Jen /Users/michal/Projects/wonderfulkb a konkrétní původní vlastněné source/test paths níže, vlastní plán/proof/learning. Žádné jiné repozitáře, externí konfigurace, instrukční soubory, nové závislosti/build framework, live AWS/provider/model/message/replay, deployment nebo task lifecycle. Zachovej ostatní rozpracované změny. Doménově kvalifikované filenames povinné, žádné state.py/utils.py/common.py/pages.py. Neoznačuj source/build jako deployed/live success.

## Přesné původní funkční požadavky a vlastnictví
Původní zadání zůstává závazným specifickým kontraktem (následující text); nový odstavec TDD pouze určuje funkční interpreter a vlastní kořenovou evidence cestu.

# Monitoring MVP: bounded čtecí odvození lifecycle

## Goal
Čisté in-memory odvození lifecycle z JEDNOHO konečného okna skutečně pozorovaných událostí. Read-domain část proposal `proposal-20261019-150954-c8891f`, `slice-retry-terminal`, bez nové stored projekce nebo tvrzení o celohistorickém latest stavu.

## Files/functions / contract
Samostatný čistý doménový `be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py` a focused test `test_monitor_lifecycle_observations.py`. Event kontrakty `2026-10-20_monitor-mvp-22-retry-terminal-events.md`, `20-publication-events.md`, RunQueued/AttemptStarted. Vstup je konečný `Sequence[Mapping[str, object]]` validovaných content-free event observations podle uvedených kontraktů, plus neprůhledný next_token předaný callerem. Existující typované event instance smí caller převést přes to_item; reducer nesmí importovat dosud neexistující event classes. V tomto řezu nepřipojuj I/O ani router a neměň audit_queries.py; skutečné napojení existujícího readeru zůstává v lifecycle HTTP zadání. Nejde o druhý reader.
- Reducer přijímá již omezené event okno z dokumentového Query, žádné vlastní I/O ani volání dalších oken. Produkuje runs/attempts observation summaries a publikované result observations s evidence event_id/sequence; rozlišuje observed start/retry/attempt terminal/run terminal, nikoli úplný execution list.
- RunQueued chybí-li, viditelné AttemptStarted/terminály neskrýt. AttemptStarted endpoint dál zůstává seznam pozorovaných zahájení, nepřepisovat jej na syntetické attempts ze summary. RunFinished bez attempt je platný; žádné doplnění nového claimu. RetryEnqueued/partial publication nezavírají run. Conflict/ztráta lease/ticho nezavírají ani pokus.
- Odlišné skutečné observations stejného runu zůstanou doložitelné. Pokud v neúplném okně chybí vztah/scope nebo terminal observations kolidují a nelze prokázat pořadí execution, vrátit unknown/ambiguous s partial evidence, ne vybrat poslední occurred_at či největší audit sequence jako absolutní business pravdu. Žádné dopočítané durations, total/pages procenta, synthetic pending nebo implicitní poslední run.
- Summary vždy coverage=partial, observation scope popsaný evaluated oknem, next_token přenést beze změny z readeru. Více oken se nesmí tiše iterovat/dopárovat. Bez snapshot/late-event úplnosti. Chybějící data unknown, nikoli nula/empty success pro read failure.
- Explicitní availability důvody: not_configured jen z reálné konfigurace, not_instrumented pouze z doložené producer/capability evidence, absence eventů sama unknown. Při nutném source failure error, který HTTP owner mapuje503. Neodhadovat konfiguraci legacy runu z dnešního environmentu.

## Boundaries
Pouze wonderfulkb. Žádná stored runs/attempts/steps/page projekce, business source fallback na mutable analýzu, Scan/unbounded replay, nový index, producer hook/identity allocator/model/cloud/deploy nebo queue/lease/retry/business změna. Doménový filename výslovně povinný, žádné runs.py/state.py/utils.py.

## Verification
Implement the TDD cycle using skill:tdd. Čisté tabulkové fake testy: start→retry→další attempt→run terminal, partial publish bez run terminal, terminal-only/max-attempt bez nového claimu, dva runy/pokusy, duplicate identity, reorder/late fragment/conflicting terminal unknown, prázdné partial okno a pokračování. Query spy potvrzuje žádné I/O/smyčku v reduceru. Not configured/instrumented/unknown/read failure odlišné, žádný syntetický complete coverage. Zachovat dřívější endpoint/reducer chování a registrované gates.

## Přesné vlastnictví zdrojů
Měň jen `audit/audit_lifecycle_observations.py` v existujícím package, `tests/test_monitor_lifecycle_observations.py` a vlastní repo-local proof/learning/plán. Beze změn audit_events.py/audit_storage.py/audit_queries.py/audit_listener.py, business callerů, společných test fixtures, routeru, YAML, závislostí a deploymentu. Tabulkové testy používají pevně specifikované event mappings, žádné placeholder třídy/importy či registr. Funkční pure reducer je deliverable, ne live HTTP integration.
