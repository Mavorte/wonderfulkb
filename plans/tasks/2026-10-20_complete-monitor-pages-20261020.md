---
title: "Monitoring pages: dokončit pure observation mapper a kontraktní testy"
type: implementation
---
# Monitoring pages: dokončit pure observation mapper a kontraktní testy

## Cíl dokončení
Nový samostatný implementační řez dokončuje nedodaný rozsah původního tasku task-b37c64cd-1783-45e6-8daf-f2e6a04e0954. Původní neúplné výsledky/proof zůstávají historické; nepřepisuj je a netvrď, že prošly. Referenční host review: plans/checkpoints/task-b37c64cd-1783-45e6-8daf-f2e6a04e0954.host-review.md.

Implementuj chybějící audit_page_observations.py; existující test nemůže importovat modul. Doplň celou původní matici včetně invalid scopes, unknown stages/types, terminal-only, cache completed/failed bez nové inference, více observations jedné stránky bez latest selection, přesný allowlist a input immutability. Pouze pure mapping konečného okna, žádný nový reader/I/O/router/HTTP delivery. Zachovej přesné vlastnictví původního tasku.

## Skutečné lokální ověření a TDD
Použij již funkční projektový interpreter `be-document-processing/.venv/bin/python` z kořene repozitáře. Ověř importy/dependency před proof capture. Z kořene repo zvol focused argv `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/` + příslušný focused test filename; RED a GREEN přesně stejné argv, proof pod vlastním přiděleným task ID v kořenovém plans/checkpoints/. Chybějící interpreter/dependency/conftest import není genuine RED. Zachovej staré artefakty a nepoužívej staré task ID k obcházení odmítnutého proof cyklu. TDD helper použij pouze prostřednictvím načtené skill:tdd a jejích skutečně povolených rozhraní, ne grep čtení externích helper internals. Při odmítnutí oprávnění nic neobcházej; uveď konkrétní capability blocker.
Focused kontroly plus plné existující registrované gates (`npm --prefix apps/backoffice test` a `npm --prefix apps/backoffice run build`) a relevantní package pytest. Neignoruj cizí neúplné tests, nevylučuj je z full gate, nezmírňuj assertions; případnou nesouvisející collection chybu přesně odliš od výsledku vlastního focused testu. Pro runtime caller testy lze stejným projektovým Python spouštět konkrétní be-validator-agent/trigger/tests, všechny AWS dependencies musí být Moto/fixtures, ne live.

## Hranice
Jen /Users/michal/Projects/wonderfulkb a konkrétní původní vlastněné source/test paths níže, vlastní plán/proof/learning. Žádné jiné repozitáře, externí konfigurace, instrukční soubory, nové závislosti/build framework, live AWS/provider/model/message/replay, deployment nebo task lifecycle. Zachovej ostatní rozpracované změny. Doménově kvalifikované filenames povinné, žádné state.py/utils.py/common.py/pages.py. Neoznačuj source/build jako deployed/live success.

## Přesné původní funkční požadavky a vlastnictví
Původní zadání zůstává závazným specifickým kontraktem (následující text); nový odstavec TDD pouze určuje funkční interpreter a vlastní kořenovou evidence cestu.

# Monitoring MVP: čisté mapování omezeného okna page observations
## Goal
Implementovat skutečnou čistou read-domain část stránkového API: explicitní content-free mapping jednoho již omezeného event okna. Vstupní sémantika: `plans/tasks/2026-10-20_monitor-mvp-12-page-outcome-events.md`, `13-attempt-pages-get.md`, `14-cache-reused-event.md`, `15-cache-reused-read.md`. Bez routeru/I/O; skutečné HTTP napojení a povinný deployment zůstávají v existujících read zadáních, nejsou tímto taskem dokončené.
## Interface a scope
Jediný nový doménový modul `be-document-processing/src/document_processing/audit/audit_page_observations.py`, jediný focused test `be-document-processing/tests/test_monitor_page_observations.py`, vlastní proof/plán/learning. Čistá funkce přijímá konečný Sequence[Mapping[str, object]] již validovaných content-free event observations + explicitní run_id a kladný attempt_no; vrací page observation items. Nevyžaduje neexistující event třídy. Caller převádí skutečné typované events přes to_item; nepřidávej druhý reader, registry/framework nebo fallback na business stav.
## Behavior
Explicitní allowlist StepStarted stage=page_transcription, PageCompleted/PageFailed a PageCacheReused. Zachovat skutečné event_id/type/sequence/occurred_at/run_id/attempt_no/page_number/stage a pouze doložené duration_ms/method/model/error_code či cached_status/cached_method/cached_model/opaque artifact_ids podle kontraktů. Cache reuse není nová inference ani nový completion. Filtr run/attempt, zachovat pořadí pozorovaného okna a terminal-only fragments. Žádná agregace latest/complete/total, vytvořené pending/start/terminal, timestamp-derived duration, business Page, text/prompt/S3 key/URL/raw exception. Absence unknown, nikoli failed. Unknown typy/stages bezpečně nepublikovat. Vstup neměnit; vracet nové allowlisted mappings. Malformed scope bezpečně odmítnout, nepřevést neplatnou observation na úspěch.
## Boundaries
Pouze wonderfulkb a výše uvedený modul/test. Neměň audit_events.py, audit_storage.py, audit_queries.py, audit_listener.py, __init__.py, společný conftest/dependencies, business worker/intake, OpenAPI ani build/deploy. Žádný cloud/provider call nebo syntetický worker proof. Názvy doménové, ne pages.py/state.py/utils.py. Žádný uložený projection/index, I/O nebo cyklus načítající další okna. Next_token zůstává u skutečného readeru/callera; toto je pouze pure item mapping.
## Verification
Implement the TDD cycle using skill:tdd. Tabulkové testy completed/failed, unknown method/model před budget-call, cached completed/failed, dvě pages/runs/attempts, terminal-only, různé observations stejné stránky bez latest inference, žádná duplicitní StepFinished událost. Přesný output allowlist a input immutability, bez business fields. Testy nad kontraktními mappings nejsou fake store ani live worker. Focused pytest a plné registrované gates zachovat; evidence skutečný RED→GREEN. Výstup není tvrzení o dokončení deployed pages GET.
