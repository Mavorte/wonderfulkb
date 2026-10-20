---
title: "Monitoring lifecycle: zachovat unscoped evidence a odmítnout rozporný ordinal fallback"
type: implementation
---
# Dokončit scope evidence reduceru

Předchozíd6b1100a má18focusedPASS/fullbackend189PASS, ale přesné původní uncertainty požadavky stále nejsou celé. Read-only review plans/checkpoints/monitoring-parallel-20261020/lifecycle-review-0923.md; NENÍ celé autoritativní: jeho řádek o dvou různých canonical attempt_no1a2 v jednomrun je chybná diagnóza — dva skutečné pokusy jsou legitimní a SAMY nesmějí být označeny ambiguous. Tuto falešnou inference výslovně odmítni, nevyráběj repair na normální retry historii.

## Skutečné zbývající mezery
- Vstupní AttemptFinished bezrun_id je nyní úplně zahozen včetně evidence. Požadavek je explicitní uncertainty/partial bez faktických domněnek; zachovat bezpečnou evidence v přiměřené stávajícímupublickontraktu unscoped/unknown reprezentaci, nevydávat malformed input za doloženěprázdnépozorování. Nevymýšlet run identity. Pokud veřejný API model dovoluje validaci odmítnutím, musí zachovat explicitně rozlišený malformedinputvýsledek/exception, ne empty success; zvol malý kompatibilní kontrakt a charakterizuj testy.
- AttemptStarted canonicalattempt_no1 spolu s legacyattempt_number2 nyní může dát určitý attempt2. Canonicalserializer legacyattempt_numberneemituje; nepřidávej nový aliasfallback. Rozporná dodaná čísla nesmí zvolit první/legacy fakt a splitnout určitésummary. Explicitní validace čiuncertainty podle canonicalinterface; při odstranění nepodporovaného aliasu zachovat všechny skutečně garantované validní veřejné vstupy, ne fixovat omyl historickéhotestu.
- Rozliš ekvivalentníduplicate od stejnéeventidentityrozdílnéhodnoty i při změněattempt_no/run scope: pouze stejná identita s konfliktním payload je konflikt. Dva odlišnéevent_id pro canonicalattempt1/attempt2jsou legitimní a mají zůstatnezávislé. Pin obě pořadí/evidence a partial/nexttoken bez syntetickýchstarts.
- Ownership pouze be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py a tests/test_monitor_lifecycle_observations.py. Žádná event/store/router/deploy změna. Zachovat18nynějšíchassertions, availabilitycaller evidence, run_status a noattemptfromRunFinished.

## Evidence a hranice
Novýtaskid genuineRED/GREEN stejnáargv přes skill:tdd povolenýinterface, staréproof/historyverdictneměnit. Projektovýbe-document-processing/.venv/bin/python; focused+fullbackend+registrovanébackofficetest/build, žádné ignore/oslabení testů. Pouze wonderfulkb ownedpaths+vlastníplan/proof/learning, noinstruction/config/dependency/tasklifecycle/git/live/provider/model/deploy. Source-onlyscope žádná runtimeclaim.

## Původní přesný funkční scope
# Monitoring lifecycle: canonical run status a neztrátová konfliktní evidence

Dokončuje nedodaný rozsah task-e7de471f-9b14-4e3d-99db-15cd8f31d8b5; nezávislý manuální root, nikoli reset historie.

## Minimální doložená oprava
Review plans/checkpoints/monitoring-parallel-20261020/lifecycle-review-0856.md:12focusedPASS, ale stále nedodaný původní reducer kontrakt. Ownership pouze be-document-processing/src/document_processing/audit/audit_lifecycle_observations.py a be-document-processing/tests/test_monitor_lifecycle_observations.py. Audit event source pouze čti.
- Canonical RunFinished emituje run_status completed|partial|failed; reducer nyní vše mapuje na finished. Zachovat skutečný status a jeho konflikty. AttemptFinished má attempt_status, nikoli outcome. Ověř skutečná to_item rozhraní, nepřebírej starou chybnou host formulaci o outcome.
- Equivalent duplicates dedup; stejný event_id+sequence s konfliktním payload nesmí potichu zahodit druhý fakt/volit dle pořadí. Výsledek musí vyjádřit ambiguity + zachovat konfliktní evidence, také pro reorder/late bounded fragments.
- Canonical attempt scope run_id+attempt_no: missing scope, invalid status a contradictory supplied identity/number nesmí vytvořit určitý výsledek, split/overwrite nebo první vyhraný údaj. Rozliš validované eventy od malformed mapping přes explicitní validaci či uncertainty podle původního API; nevymýšlej nový uložený event kontrakt/legacy aliases.
- RunFinished optional attempt_no není sám attempt event: nevyrob attempt z pouhého run terminálu. Terminal-only AttemptFinished je naopak legitimní, ale nedoplňuje start ani úplnost historie. Run/attempt/publikace zůstávají oddělené.
- not_configured/not_instrumented jen s explicitní caller evidence dle původního scope; prázdno je unknown. Read failure vyjádřit explicitním chybovým výsledkem/výjimkou pro pozdější HTTP503 mapování, ne empty success; reducer žádné I/O ani HTTP neprovádí. Nevyžaduj konkrétní nový parametr/error framework, zvol malý public contract a charakterizuj jej testy.
- Zachovat 12 nynějších případů, doplnit právě tyto prokazatelné mezery a původní požadovanou scope/evidence/availability matici. Coveragepartial, opaque token a žádné absolute/latest inference.

## Evidence, ověření a hranice
Jde o nový explicitně vyžádaný samostatný dokončovací root. Historické failed acceptance infra_inconclusive/incomplete_diff_visibility a staré TDD proof zachovat; žádné přepisování či vydávání historie za ACCEPT. Vlastní nový task ID a vlastní RED/GREEN proof, stejná argv, genuine RED na chybějící sémantiku, ne dependency nebo collection failure. Použij skill:tdd přes její povolený interface, nikoli obcházení permissions/čtení externích helper internals. Již funkční be-document-processing/.venv/bin/python; bez systémového fallback.
Focused test plus relevantní plná be-document-processing/tests sada, npm --prefix apps/backoffice test a npm --prefix apps/backoffice run build. Zachovat všechny existující assertions, nepřidávat collection ignore nebo maskovat cizí failure. Skutečný unrelated blocker odliš od vlastních výsledků. Artefakty checkpoints pouze Markdown/JSON evidence, žádné executable skripty či kopie source.
Pouze wonderfulkb, přesně vlastněné source/test paths a vlastní plán/proof/learning. Žádné instrukční/config/dependency/framework/task lifecycle/git kroky, live AWS/provider/model/replay/deploy nebo změna jiných source modulů. Source-only scope, nevyžaduje nasazení ani live HTTP; žádné tvrzení source testů jako runtime success. Nové moduly nepřidávat; žádné utils.py/state.py/common.py.

## Původní přesný funkční rozsah (závazný, oprav výše jen jeho mezery)
# Dokončit lifecycle reducer podle skutečného event kontraktu

## Cíl a doložený problém
Dokončit pure reducer nedodaný v task422c4f83. Host review plans/checkpoints/acceptance-host-review-0818-read-reducer.md. Šest focused testů prochází, ale nechrání skutečný event interface:
- Skutečný AttemptFinished předává run_id + attempt_no + outcome (ověř přesný nynější serializer); reducer skupinuje jen attempt_id/attempt_number/attempt_status. Syntetický validní terminal-only attempt s run_id=r,attempt_no=1,outcome=failed vrací attempts=(). Oprav proti canonical public scalar map, ne vytvořením jiného event kontraktu.
- Jeden AttemptFinished s attempt_status=completed v historickém vstupu dává ambiguous, protože současně přičítá obecný finished i konkrétní status. Rozliš skutečné konfliktní výsledky od jedné konzistentní informace. Podporu starých jmen přidej pouze pokud původní konkrétní contrat opravňuje, nevymýšlej fallback cascade.
- Explicitní evidence/sequence/scope, nejistota při missing/conflicting scope/status, availability/read failure dle původního scope, duplicate/reorder/late fragments. Nevol první attempt number a neclaimuj absolutní latest. Terminal-only nevyrobí start ani completion celé historie.
- Doplň skutečnou celou původní matici, ne jen šest happy/basic testů. Pure mapper/reducer nesmí vyvíjet jiné event/store/router moduly. Ownership pouze audit_lifecycle_observations.py a test_monitor_lifecycle_observations.py, plus vlastní evidence.

## Ověření, evidence a hranice
Použij projektový `be-document-processing/.venv/bin/python` z kořene repo; pytest zde načítá src přes conftest, pro přímé syntetické probe nastav explicitně `PYTHONPATH=be-document-processing/src`. Nepoužívej systémový python/python3 ani fallback, který způsobil původní nesémantický RED. Ověř závislosti před capture. Pracuj pod NOVÝM vlastním task ID, vlastní plans/checkpoints/<task-id>.red-green-proof.md; staré failed proof/history se nesmí přepisovat, mazat nebo vydávat za green. Genuine RED je požadovaná chybějící vlastnost, ne dependency/collection/environment chyba; stejná argv pro RED/GREEN. Načti skill:tdd a použij skutečně podporované rozhraní, ne čtení zakázaných helper internals nebo obcházení oprávnění. Capability denial je konkrétní blocker.
Spusť jednotlivé focused testy, celou příslušnou audit matici i plné `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests`, pak registrované `npm --prefix apps/backoffice test` a `npm --prefix apps/backoffice run build`. Nevyřazuj failing tests ani nesnižuj assertions, nevytvářej collection ignores; odliš unrelated blocker od vlastního výsledku. Testy kvality kontraktu nesmí slepě vyžadovat ValueError tam, kde Python odmítá chybějící/nepovolený argument TypeError; oprav očekávání pouze proti explicitní sémantice neplatného vstupu, ne pro zakrytí skutečné validace.
Pouze wonderfulkb a níže vymezené source/tests plus vlastní task plan/proof/learning. Žádná instrukční/config/platform/task lifecycle změna, nový runtime/dependency/framework ani přístup do jiných repo. Exact module names domain-qualified; žádné utils.py/common.py/state.py/runs.py. No live provider/queue/replay/inference/business writes. Jen HTTP slice níže zachovává své specifické standing test-deploy+live povolení a povinnosti; pure domain slices nic nenasazují. Zachovej ostatní rozpracované source a historické artefakty.

## Původní přesný kontrakt
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
