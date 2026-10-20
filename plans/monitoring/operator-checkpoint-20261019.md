# WonderfulKB monitoring — odložená registrace 19. 10. 2026

## Rozsah zadání
Uživatel 20:30 schválil projednané run_context parametry a chce malé tasky ve zvláštním batchi, zatím bez spuštění. Tato instrukce neaktivuje implementaci ani běžné projektové nasazovací kroky. Starší Case Client batch a jeho výsledky se nepřepisují.

## Návrh a provoz nejsou totéž
Proposal proposal-20261019-150954-c8891f, API průvodce a OAS revize 0.3.2 obsahují odsouhlasený kontext. Zdrojový review doložil sémantické hooky checked-in pipeline, nikoli živé propojení s intake. Parametry nejsou otevřené produktové otázky; níže jsou skutečné technické prerequisite.

## Host readiness před budoucím dispatch
- Z veřejného task/batch owneru ověřit aktuální pořadí, stav, runtime a překryvy; zachovat default pauses a neaktivní batch, dokud uživatel nepožádá o spuštění. Nezavádět manual holds jen kvůli této poznámce.
- Vstupní producer-contract report smí vycházet jen z dostupných zdrojových artefaktů. Host musí odděleně doložit skutečný analysis producer/worker, ingest commit a použitelný audit routing i důvěryhodnou case/content autorizaci. Unknown v reportu není napojení. Nepropouštět implementaci závislou na nedodaném technickém vstupu a nenahrazovat oprávnění API klíčem nebo browser claims. Host operace patří hostu, ne novému coding tasku.
- Cursor prototyp musí doložit konkrétní bounded persistence/index/read pattern a možnost pozdějšího nalezení eventu se starším occurred_at; pouhé overlap okno, wall-clock UUID nebo stále dokola celý scan nejsou důkaz. Review kontraktu spotřebují storage/history/UI tasky.
- Artefakty plans/monitoring/producer-contract.md a journal-access-contract.md jsou technické vstupy, nikoli požadavek workerů kontrolovat stav jiných tasků. Žádné obcházení review/acceptance/plných registered gates.
- Source-only testy a Moto nedokládají live AWS. Při pozdější autorizované aktivaci dodržet standing AWS test deployment instrukci z AGENTS.md: instalace, in-place deployment a skutečné HTTP/data ověření vlastní host. Nyní žádný deploy ani inference/replay/business write. U UI zachovat Wonderful SDK/platform owner a samostatné publication hranice.

## Rozpad
18 behaviorálních řezů, jednou registrovaných ve wonderfulkb-document-monitoring-20261019, řazení dle registration-20261019.json. Rozsah 200–245 slov/brief. Výjimka z doporučených 2–6 kroků je záměrná: uživatel požaduje jeden speciální batch a malé tasky; neslučovat hooky do megatasku jen kvůli počtu členů. Jde o nové independent roots, nikoli děti historického selhání. Bez model override, běžná routing/approval politika. Automatická estimatedSize implementací nemusí existovat před planningem; netvrdit neexistující S odhad a nevynucovat ho.

## Kontrola překryvů
Před registrací veřejný project list obsahoval 14 historických Case Client tasků, všechny terminal (done/cancelled/failed); canonical briefy neměly processing-monitor/FileReceived/audit scope. Žádný nový monitoring task ani aktivní projektový runtime phase. Některá terminal metadata obsahovala staré PID; to samo není běžící runtime ani důvod k opravě. Sdílený existující awsApi.ts a CaseDetail.tsx se mění až v budoucnu sekvenčně. Nesouvisející opencode.json, acceptance evidence a execution.lock ponechány beze změny.

## Validace nynější dokumentové práce
YAML parse rev0.3.2 a 124 lokálních $ref, 12 paths; kontrola odstranění zastaralých formulací o neschválených parametrech ve všech třech souborech. Briefy mají matching frontmatter/H1 a pět částí, žádné worker lifecycle ani version-control instrukce. git diff --check bez nálezů. Runtime ani implementace netestovány, protože nebyly spuštěny. Proposal lint je globální; ostatní historická findings nejsou součást této změny a nebyla opravována.

## Finální stav registrace
Veřejný batch.status + task.list a jednotlivé task.info: 18 členů / 18 independent roots, pořadí 1–18, nextAppendSeq=19, inactive, všichni backlog + pauseState=default, paused=true, bez PID/session/modelOverride. Každý má vazbu na proposal/sekci. Žádný start, manual pause ani lifecycle override použit. Plný index v task-index-20261019.md, receipts a brief SHA256 v registration-20261019.json.

## MVP follow-on 19. 10. 22:22
See mvp-reference-20261019.md: all monitoring GET use existing intake FastAPI/App Runner, not new Gateway/Lambda. First FileReceived is now four smaller briefs (store, hook/build, GET, AWS smoke), not large A/B plus RunQueued. Live trigger source/run identity and trusted case authorizer remain concrete unresolved technical inputs; do not equate API key with case rights or old DocumentService with live trigger. Only prompt/lifecycle cleanup authorized now, no start/deploy. Old18 cancellation preserves markdown/hash references; current facts live in public task/batch state and mvp-revision evidence.

Verified result: `mvp-revision-verification-20261019.json` supersedes the initial A/B registration snapshot. Old18 cancelled with unchanged brief hashes; old batch terminal classification complete reflects cancellation, not delivery. New4 canonical files monitor-mvp-01..04, all FileReceived, reestimated M, backlog/default-paused; new batch inactive and no runtime. No code/build/deploy claimed.
