---
title: "Monitoring runtime: skutečná producer integrace nad doloženým execution rozhraním"
type: implementation
---
# Skutečná producer integrace

Dokončuje nedodaný funkční scope821fe70a, nový explicitní manuální root. Předchozí runtime správně nic neimplementoval: chybí schválený execution-owner interface, aktualizace blocker dokumentace sama NENÍ funkční dodávka. Přesný známý technický vstup je v plans/monitoring/runtime-producer-context-contract.md a plans/checkpoints/task-821fe70a-e40f-4fc9-bd11-ced0e5183dde.checkpoint.md. Vyžaduje stable logical run identity, atomic claim→attempt ordinal, confirmed/ambiguous enqueue result a immutable context/provenance z reálného execution owner rozhraní. Nevol UUID/hash/time fallback ani vlastní counter/outbox/lease/fencing/queue schema bez schváleného kontraktu.

Výstupem jsou skutečné minimální caller+listener code integration a differential NoOp/functional/failing sink tests na return/write/order/exceptions, ne další ekvivalentní blocker poznámka. Chybějící skutečný technický interface nelze nahradit povolujícím test doublem; chybějící bezpečný input zůstává konkrétní blocker. Operátorské držení/dispatch není úkol workeru.

Zachovat historické failed acceptance/proof/TDD a původní scope; vlastní novýID genuine RED/GREEN přes povolené skill:tdd rozhraní. Designovaný projektový interpreter+funkční package cwd/importy před capture; dependencies/collection nesmí být označeny za funkční RED. Nepřepisovat minulou historii. Všechny registrované gate povinnosti zůstávají, žádné provider/live/model/replay/deploy ani nový runtime framework nebo permission bypass.

## Původní celý deliverable a přesné hranice
# Nedodaný runtime producer context

## Přesný aktuální stav
Původní535479cc znovu skončil jen aktualizací plans/monitoring/runtime-producer-context-contract.md; žádná source integrace. Historická opakovaná diagnóza je již známá, znovu ji nevydávej za dokončenou implementaci. Funkční enqueue/claim/run_document interface pořád chybí. Zachovej source, plán, proof, staré verdicts a tento blocker kontrakt.
Technický vstup dodávky je konkrétní schválený execution-owner interface: stabilní logical-run identity a atomic claim→attempt_no, confirmed/ambiguous enqueue výsledek, immutable context a canonical caller/build provenance. Žádná volba counter/outbox/fencing/lease/queue schema bez explicitního schváleného kontraktu, UUID/hash/timestamp jako fake identity ani auth permission bypass. Chybějící owner rozhodnutí nelze vyřešit stejným opakovaným dokumentačním cyklem nebo test doublem.
Jakmile skutečný kompatibilní technický kontrakt existuje, dokončit minimální thin scalar integration do existujících callerů a package listeneru; NoOp/functional/failing sink differential tests musí prokázat stejná businesswrite/order/return/exceptions. Pokud konkrétní approved source seam stále neexistuje, vrať přesný rozhodovací vstup a žádné fake source-complete; toto zadání samo neopravňuje změnit execution semantics.

## Test prostředí a evidence
Projektový be-document-processing/.venv/bin/python, genuine vlastní novýtaskid RED/GREEN se stejnou argv a funkčním dependency setup, žádný systémový fallback a žádné přepisování minulých proof. Pro validator suite použij canonical package cwd/PYTHONPATH, aby backfill import skutečně fungoval (předešlý root invocation collection error není product GREEN ani funkční RED). Run focusedcaller/store/sink testy a registrované backoffice test/build. Žádné live/replay/provider/inference/deploy/scheduler/lifecycle/sourcejinýchprojektů.

## Původní přesný deliverable a hranice
# Monitoring runtime: dokončit doložený producer a immutable execution context

## Cíl dokončení
Nový samostatný implementační řez dokončuje nedodaný rozsah původního tasku task-626722a4-f9fd-46a9-8304-17b9f24de1cc. Původní neúplné výsledky/proof zůstávají historické; nepřepisuj je a netvrď, že prošly. Referenční host review: plans/checkpoints/task-626722a4-f9fd-46a9-8304-17b9f24de1cc.host-review.md.

Stávající práce je pouze plans/monitoring/runtime-producer-context-contract.md, nikoli source integration. Dokonči přesně původní deliverable jen nad skutečným doloženým canonical caller/build a autoritativním interface. Nutné confirmed/ambiguous enqueue outcome + stabilní logical run identity, atomický claim/attempt result bez nového pokusu při failed claim, immutable context forward ke skutečnému run_document, skutečné NoOp/functional/failing-listener differential tests. Stávající kontrakt uvádí, že interface v této podobě neexistuje. Nový požadavek na dokončení NENÍ schválením dříve zakázané execution změny: žádný spekulativní counter/runtime tabulka/outbox/fencing/queue-schema nebo lease/retry změna. V plánování nejprve odliš doložitelný kompatibilní source seam od chybějícího konkrétního execution-owner rozhodnutí; pokud chybí, vrať přesný minimální kontrakt/rozhodnutí jako blocker, nevydávej dokumentaci/no-op za implementaci. Nevytvářej falešné runtime identity ani TDD. Repo-local module files musí být domain-qualified. Explicitní nevyřešená interface hranice z původního briefu zůstává.

## Skutečné lokální ověření a TDD
Použij již funkční projektový interpreter `be-document-processing/.venv/bin/python` z kořene repozitáře. Ověř importy/dependency před proof capture. Z kořene repo zvol focused argv `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/` + příslušný focused test filename; RED a GREEN přesně stejné argv, proof pod vlastním přiděleným task ID v kořenovém plans/checkpoints/. Chybějící interpreter/dependency/conftest import není genuine RED. Zachovej staré artefakty a nepoužívej staré task ID k obcházení odmítnutého proof cyklu. TDD helper použij pouze prostřednictvím načtené skill:tdd a jejích skutečně povolených rozhraní, ne grep čtení externích helper internals. Při odmítnutí oprávnění nic neobcházej; uveď konkrétní capability blocker.
Focused kontroly plus plné existující registrované gates (`npm --prefix apps/backoffice test` a `npm --prefix apps/backoffice run build`) a relevantní package pytest. Neignoruj cizí neúplné tests, nevylučuj je z full gate, nezmírňuj assertions; případnou nesouvisející collection chybu přesně odliš od výsledku vlastního focused testu. Pro runtime caller testy lze stejným projektovým Python spouštět konkrétní be-validator-agent/trigger/tests, všechny AWS dependencies musí být Moto/fixtures, ne live.

## Hranice
Jen /Users/michal/Projects/wonderfulkb a konkrétní původní vlastněné source/test paths níže, vlastní plán/proof/learning. Žádné jiné repozitáře, externí konfigurace, instrukční soubory, nové závislosti/build framework, live AWS/provider/model/message/replay, deployment nebo task lifecycle. Zachovej ostatní rozpracované změny. Doménově kvalifikované filenames povinné, žádné state.py/utils.py/common.py/pages.py. Neoznačuj source/build jako deployed/live success.

## Přesné původní funkční požadavky a vlastnictví
Původní zadání zůstává závazným specifickým kontraktem (následující text); nový odstavec TDD pouze určuje funkční interpreter a vlastní kořenovou evidence cestu.

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

## Přesné vlastnictví zdrojů
Vlastni pouze skutečný source caller/context pod `be-validator-agent/`, příslušné vlastní focused testy a `plans/monitoring/runtime-producer-context-contract.md`. V tomto řezu neměň `be-intake/`, audit event/storage/query/listener moduly, YAML, globální dependency/build konfiguraci ani cloud. Použij již existující injektovatelný listener port, pokud skutečný canonical caller a autoritativní identity existují; doplnění centrální audit implementace a společného build wiring patří integračnímu řezu. Neexistující execution interface zaznamenej přesně jako technický blocker podle Required work, nikoli fiktivní hotovou integraci. Neměň business execution kvůli monitoringu.
