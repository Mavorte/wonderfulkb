---
title: "Monitoring OpenAPI: opravit YAML a dokončit přesné observation DTO kontrakty"
type: implementation
---
# Monitoring OpenAPI: opravit YAML a dokončit přesné observation DTO kontrakty

## Cíl dokončení
Nový samostatný implementační řez dokončuje nedodaný rozsah původního tasku task-e0275532-1050-49c2-b1e3-b787751549bf. Původní neúplné výsledky/proof zůstávají historické; nepřepisuj je a netvrď, že prošly. Referenční host review: plans/checkpoints/task-e0275532-1050-49c2-b1e3-b787751549bf.host-review.md.

Oprav aktuální neparsovatelný YAML (ověřeně řádek66, col51) a dokonči kontrakt, ne pouze syntaxi. Nahraď generický nespecifický ObservationItem přesnými per-event/per-operation allowlisty: FileReceived bez run scope, run/attempt/page fields pouze správným typům. Lifecycle runs/detail/audit musí mít vlastní DTO vyjadřující unknown/ambiguous/partial, evidence a publication oddělenou od terminalu. Explicitní error responses 400/403/404/503 s private,no-store. Nepřenášej dnešní rozpor testu vyžadujícího generické details do nového kontraktu; test assertions odvoď z původních specifických briefů, ne z vadného návrhu. Parse+ref+schema validace musí skutečně proběhnout. Stejný jediný YAML, žádná route implementation/deploy.

## Skutečné lokální ověření a TDD
Použij již funkční projektový interpreter `be-document-processing/.venv/bin/python` z kořene repozitáře. Ověř importy/dependency před proof capture. Z kořene repo zvol focused argv `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/` + příslušný focused test filename; RED a GREEN přesně stejné argv, proof pod vlastním přiděleným task ID v kořenovém plans/checkpoints/. Chybějící interpreter/dependency/conftest import není genuine RED. Zachovej staré artefakty a nepoužívej staré task ID k obcházení odmítnutého proof cyklu. TDD helper použij pouze prostřednictvím načtené skill:tdd a jejích skutečně povolených rozhraní, ne grep čtení externích helper internals. Při odmítnutí oprávnění nic neobcházej; uveď konkrétní capability blocker.
Focused kontroly plus plné existující registrované gates (`npm --prefix apps/backoffice test` a `npm --prefix apps/backoffice run build`) a relevantní package pytest. Neignoruj cizí neúplné tests, nevylučuj je z full gate, nezmírňuj assertions; případnou nesouvisející collection chybu přesně odliš od výsledku vlastního focused testu. Pro runtime caller testy lze stejným projektovým Python spouštět konkrétní be-validator-agent/trigger/tests, všechny AWS dependencies musí být Moto/fixtures, ne live.

## Hranice
Jen /Users/michal/Projects/wonderfulkb a konkrétní původní vlastněné source/test paths níže, vlastní plán/proof/learning. Žádné jiné repozitáře, externí konfigurace, instrukční soubory, nové závislosti/build framework, live AWS/provider/model/message/replay, deployment nebo task lifecycle. Zachovej ostatní rozpracované změny. Doménově kvalifikované filenames povinné, žádné state.py/utils.py/common.py/pages.py. Neoznačuj source/build jako deployed/live success.

## Přesné původní funkční požadavky a vlastnictví
Původní zadání zůstává závazným specifickým kontraktem (následující text); nový odstavec TDD pouze určuje funkční interpreter a vlastní kořenovou evidence cestu.

# Monitoring MVP: jeden přesný OpenAPI kontrakt event observations
## Goal
Upravit jediný již existující `be-document-processing/contracts/openapi-processing-monitor.yaml` na přesný soubor malých API-only observation-window kontraktů ze stávajících monitor-mvp briefů 03,07,09,11,13,15,17,19,21,24. Současný širší YAML není mandát pro nové endpointy/projekce. Konkrétní sémantika všech typů v monitor-mvp event brief 06,08,10,12,14,16,18,20,22, reducer23; proposal `proposal-20261019-150954-c8891f`. Záměrně specifikace kontraktu, nikoli implementace/nasazení routeru.
## Scope
Výhradně tento YAML a nový focused contract test `be-document-processing/tests/test_monitor_openapi_observation_contract.py`, vlastní proof/plán/learning. Needituj audit source, router/main, worker/build/dependency/conftest, jiné zadání ani instrukce. Žádný druhý YAML, deployment nebo cloud call. YAML musí zůstat valid OpenAPI s resolveable refs; reuse již dostupné offline dependency, nepřidávej framework.
## Required semantics
Jen dokumentové events, run-events, pozorované AttemptStarted attempts, steps, pages a přesný bounded lifecycle runs/run-detail/document-audit read z brief24 (tyto tři operations jsou scope, nikoli starý celohistorický business registr). Rozliš požadované vs skutečně nasazené operace v description; contract není deployment evidence. Items/next_token/observed_at; kde vyžadováno coverage=partial. Limit1–100, explicitní run/attempt scope, opaque operation-bound last-evaluated token, empty items s continuation. Jeden bounded event window, žádné snapshot/incremental/complete/latest garance, totals či celohistorická agregace. Přesné typy/schema allowlist bez content/raw errors/S3 keys; terminal-only fragment, PageCompleted/PageFailed jediný page terminal, cache reuse ne nová inference, publication ne automatický run terminal. Lifecycle unknown/ambiguous/partial odpovídá23/24, žádné synthetic starts/attempts/statusy. FileReceived zůstává bez run scope.
Důvěryhodná identity→case authorization je nutná interface, ne falešné oprávnění ze shared key. 400/403/404 podle doložené politiky a503 required-read failure, private,no-store i chyby. Nespecifikuj vymyšlený nový auth framework/provider ani předstírané dostupné claims. Jestli přesná existující auth politika nelze doložit, označ konkrétní unavailable interface v popisu místo oslabení hranice. Skutečnou route dodávku, deployment a HTTP proof neruš; nejsou scope této kontraktové úlohy.
## Verification
Implement the TDD cycle using skill:tdd. Focused offline test parse+refs/path/param/schema assertions na konkrétní chybný širší kontrakt, skutečný RED→GREEN. Ověř required fields, allowlists, partial/empty continuation, no content, bez dalších širších business run list/detail mimo přesně uvedený bounded lifecycle kontrakt24 a bez artifact/content paths. Plné registrované gates zachovat. Pouze repo-local evidence, žádný deploy/live success claim.
