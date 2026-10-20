---
title: "Monitoring MVP: bounded čtecí odvození lifecycle"
type: implementation
---
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
