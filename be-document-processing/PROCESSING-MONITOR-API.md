# Monitoring dokumentů — API-only slices a pracovní kontrakt

**MVP revize podle požadavku 19. 10. 2026 ve 22:22.** Podrobnosti a zachované reference: [MVP kontrakt](../plans/monitoring/mvp-reference-20261019.md). První FileReceived slice rozdělit na store → upload hook/build → jeden GET → jednoduchý AWS smoke. Další slices jsou roadmap, ne acceptance prvního přírůstku.

**Aktuální scope 19. 10. 2026: pouze monitoring API, deset malých vertikálních slices. Žádné UI, business list/detail ani artifact-content API. Návrh, nikoli důkaz implementace nebo nasazení.**

Autoritou je [proposal monitoringu](../docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md), zejména `data-model`, `instrumentation`, `read-api`, `delivery` a jednotlivé `slice-*`. Předchozí [OpenAPI YAML 0.3.2](contracts/openapi-processing-monitor.yaml) obsahuje překonaný širší scope. Jeho business collection/detail, artifact-content a UI předpoklady **nejsou součástí aktuálního kontraktu ani oprávněním k implementaci**. Jediný existující YAML se cíleně zúží v tasku prvního API; nevytváří se druhý paralelní kontrakt. Aktuální pravidla níže a proposal mají do té doby přednost. Existence návrhové operace neznamená, že je nasazená.

## Ownership a skutečné hranice

Audit je interní Python package `be-document-processing/src/document_processing/audit/`, nikoli nová aplikace, root modul, proces, deploy jednotka nebo obecný event bus. Business vlastní existující upload, dokumentová metadata, analysis, job/lease, originály, cache a výsledky. Jejich tabulky, klíče, obsah a lifecycle se nemění. Audit do nich nepřidává business pole ani jejich kopie. Aktuální AWS business struktura má přednost před historickým checked-in adapterem; [průzkum rozdílů](../docs/architecture/document-processing-aws-contract-differences.md) je vstup, ne migrační zadání.

Audit ukládá jen append-only Event do vlastní úzké auditní tabulky dle proposalu; run/attempt/step/page/snapshot jsou odvozené runtime pohledy. Malý rebuildable index/projekce je dovolený jen pro konkrétní bounded dotaz, ne jako další plný manifest. Runtime job/lease zůstává execution ownerem. Žádný nový scheduler ani business job backend.

Přístup `composition root → business + audit listener`; business zná malý injektovaný protokol, nikoli boto3/audit itemy/retenci/catch-retry logiku. Stávající návrhové názvy `audit_events.py`, `audit_listener.py`, `audit_storage.py`, `audit_queries.py` jsou doménové; nevytvářet generické `events.py`, `storage.py`, `utils.py`. Jen potřebný slice, ne celý framework předem.

## Nekritický fail-open zápis

Veškerý audit je best-effort. Chyba tvorby obálky, serializace, předání nebo persistence nesmí změnit business odpověď, výjimku, upload commit, publish, queue send, retry ani lease. Izolaci vlastní auditní hranice; krátký konečný I/O timeout bez auditní retry smyčky nebo neomezených SDK retries. Žádný durable outbox, fronta nedoručených auditů, recovery/replay, periodický heartbeat ani čekání na obnovu sinku. Bez společné audit+business transakce.

Ztráta eventu je přijatelná a nemusí být zjistitelná. Absence eventu neprokazuje neprovedení business akce; nepozorovaný konec je unknown, rozpoznané mezery partial. Nedopočítávat z aktuálního business snapshotu fiktivní historii ani neinferovat mrtvého workera z absence aktivity.

### Event a data

Obálka: `schema_version`, `event_id`, `case_id`, `document_id`, `sequence`, `type`, `occurred_at`. `FileReceived` nemá run_id, ostatní schválené typy run_id vyžadují; attempt/stage/page/correlation scope pouze dle konkrétního eventu. Pouze `occurred_at` je čas události na skutečné hranici akce. **Neukládat čas zápisu/doručení auditu ani recorded_at.** Sequence/revision je technická pozice, ne čas, kauzalita nebo garance úplnosti. Timeline řadí `occurred_at,event_id`.

Bez názvu souboru, MIME, velikosti, uploadéra, titulu, label/confidence, textu, vytěžených hodnot, promptů, raw provider odpovědí či celých job/config/result objektů. Error jen bezpečný kód/mapovaný popis, nikoli libovolná výjimka s obsahem dokumentu. Veřejné reference jsou opaque ID, ne interní bucket/key, credentials nebo download URL.

Schválená sada 13 typů: `FileReceived`, `RunQueued`, `AttemptStarted`, `StepStarted`, `StepFinished`, `StepFailed`, `PageCacheReused`, `PageCompleted`, `PageFailed`, `ResultPublished`, `RetryEnqueued`, `AttemptFinished`, `RunFinished`. Schválená mapa source hooků a významů je v proposalu; nedodávat všechny najednou.

- FileReceived až po úspěšném S3 a metadata commitu skutečného intake (`be-intake/app/main.py`, kolem 201–250). Duplicate, S3-only a failed metadata commit nejsou přijetí. Intake image dnes samotný package neobsahuje; reálné import/build propojení je součást upload-hook/build tasku, ne předpoklad.
- RunQueued až po úspěšném skutečném enqueue, nikoli pouhé založení jobu nebo local no-op; není worker start. Živá AWS cesta je wonderfulkb-trigger-enqueue (`trigger.enqueue_handler.handler` → `common.enqueue_document`), jejíž canonical source v tomto checkoutu nebyl doložen. Staré service.py/bootstrap.py nejsou důkaz živého hooku; před zadáním tohoto přírůstku doložit zdroj a run identitu.
- AttemptStarted až po potvrzeném owned claim a inkrementu, nikoli pouhém doručení.
- RetryEnqueued až po potvrzeném skutečném opětovném enqueue (`pipeline.py` kolem 131–132 a 145–146), ne při záměru retry.
- Kroky/stránky/cache/publish/terminální scope jsou postupně další slices. Cache reuse nedokazuje novou inferenci ani původní cache run; retry končí pokus, ne běh.

### Historický kontext RunQueued

Nejvýše jednou, jen známé hodnoty uloženého jobu nebo dostupná neměnná reference: `mode`, `pipeline_version`, `prompt_version`, `ocr_model`, `extraction_model`, `provider`, `api` z bedrock_api a `region` z bedrock_region. `job_id` a `config_hash` jsou volitelná diagnostika. Reference konkrétního vstupu veřejně `source_artifact_id` v artifact_ids, interně jen potřebná známá verze/hash. Chybějící nebo zaniklé hodnoty jsou unknown/unavailable, ne dnešní environment nebo mutable současný obsah.

Konfigurace modelu neprokazuje jeho volání; deklarovaná verze není source/prompt hash; config_hash nelze převést na config. Signature konfigurace v dnešním uloženém job.config není: žádná kompletní reprodukovatelnost všech kroků. Historické obsahy, artifact list/content a presigned downloads jsou odložené; opaque provenance není příslib stažení.

## API operace a postupné dodání

Jeden monitoring router v existujícím Python/FastAPI `be-intake` na App Runneru (ne nová Lambda/API Gateway): `/v1/cases/{case_id}/processing/documents`.

1. Slice FileReceived: `GET /{document_id}/events`, document scope bez runu.
2. Slice RunQueued MVP: jediný nový `GET /{document_id}/runs/{run_id}/events`. Filtr stejného deníku, bounded evaluated-window; empty stránka s next_token je legitimní. Run list/detail, run index a široký context snapshot jsou odložené. Producer hook/live smoke nejsou ready bez canonical source/run identity; viz plans/monitoring/live-trigger-evidence-20261019.md.
3. Slice AttemptStarted: `GET /{document_id}/runs/{run_id}/attempts` jako bounded stránka pozorovaných AttemptStarted (event_id, attempt_no, occurred_at), ne úplná execution projekce. Bez stored projection, totals nebo terminal souhrnu. Deployed claim nemá attempt counter: producer hook/live smoke vyžadují doložený execution kontrakt.
4. Slice source_validation: `GET /{document_id}/runs/{run_id}/steps?attempt_no=...`.
5. Slice page outcome: `GET /{document_id}/runs/{run_id}/pages?attempt_no=...`.
6.–9. Cache reuse, extraction, signature detection a result publishing rozšíří doložené eventy/projekce; žádné automatické content endpointy.
10. Retry/terminal lifecycle: `GET /{document_id}/audit` až se skutečným observed lifecycle souhrnem.

Neimplementovat nový `GET /processing/documents`, business `GET /processing/documents/{document_id}`, union Upload/Analysis DTO, business status filtry, `/{document_id}/artifacts` ani `/artifacts/{artifact_id}`. Existující entity API a oprávnění ke korekcím/obsahu zůstávají beze změny. Žádné obrazovky, frontend/proxy projekt nebo klientský polling.

## Bounded čtení, dostupnost a bezpečnost

- MVP kolekce má bounded `limit` a scope/query-bound opaque `next_token`, stabilní pořadí. Refresh začíná nové stránkování od začátku; bez incremental polling, revision/fencing a garance zachycení pozdního insertu během staré stránkovací relace. Žádný Scan. Neslibovat snapshot/úplnost. Scope/token chyby nesmějí uniknout do cizího case/run.
- `observed_at` je čas čtení, nikoli heartbeat. Odvozená freshness/coverage a neznámé hodnoty nullable; unknown není nula, business failed nebo hotovo.
- Odlišit not_configured, not_instrumented a skutečně empty. Potřebný read-source failure je 503, ne úspěšné `items=[]` nebo vymyšlená absence.
- Neexistující identita/scope 404; nepovolený přístup 403 nebo konzistentní existence masking dle ověřeného skutečného auth kontraktu. Samotný API klíč ani existence case nejsou case oprávnění. Ověřit podporovaný autentizovaný server/case-authorizační seam na prvním dotčeném API. Credentials server-only; nenahradit chybějící security seam dummy stubem.
- Všechny odpovědi včetně chyb `Cache-Control: private, no-store`. Žádné dokumentové hodnoty nebo credentials do Mission Control/reportů.
- Schválený SERVICE seam je implementován společně v `be-intake/app/processing_monitor_authorization.py` a `processing_monitor_routes.py`: serverový Bearer digest → SERVICE principal → explicitní case grant, fresh Secrets Manager policy, exact consistent metadata membership nebo ověřený retained tuple. Pro document-events chybějící/forged identita a grant403, neznámý document404, request/cursor400, required read failure503; podrobná konfigurace/rotation v intake README. Upload klíč zůstává samostatný.
- **Otevřený kontraktový gate:** existující bounded reader stránkuje podle `EVENT#event_id`, nikoli globálně podle `occurred_at,event_id`. Tento rozdíl není schválenou změnou chronologického požadavku proposalu a blokuje jeho acceptance. Lokální sort jedné stránky tento problém neřeší; source/test/image důkaz není chronologický ani live důkaz.
- Region `eu-central-1`. Navržených 30 dní event retence vyžaduje potvrzení vlastníka dat; neaktivovat nepotvrzené mazání. Odvozené indexy nesmějí po expiraci zdrojů předstírat dochovanou historii. TTL nikdy nesmaže jediný audit korekcí nebo business výsledek.

## Malé tasky a důkaz dodávky

První slice má čtyři úzké dodávky: audit store; skutečný FileReceived hook a package build; jeden GET; jednoduchý AWS upload→HTTP smoke. Původní velké A/B briefs jsou překonané. RunQueued/AttemptStarted mají samostatné malé kontrakt/read části dle MVP reference; skutečné producer hooky a AWS smoke vyžadují doložený canonical source a execution identity. Další schopnosti zůstávají roadmap. Starou osmnáctitaskovou sadu zrušit, markdown zachovat pro reference, zejména sedmičku.

Cílené testy happy path, duplicate/fail-open a auth/scope/read-error místo plošných matic. Registrované gates se nemění. První funkční slice je dodaný až po skutečném nasazeném upload→GET smoke; dokončení source podtasku není nasazený úspěch. Nepožadovat cloud fault injection, komplexní refresh ani mnoho endpointů v jednom tasku.

Coding pipeline vlastní source a testové opravy. Host vlastní instalaci a guarded in-place deployment existujícího AWS test cíle dle AGENTS.md včetně provenance/recovery. Credentials server-only, žádné replay reálných dokumentů, obcházení auth nebo neautorizovaná placená inference. Tato revize pouze mění zadání, nic nespouští.

Doplnění sekcí2/3: název Processing Monitor API; stejné umístění a konkrétní malé části v `plans/monitoring/mvp-reference-20261019.md` § Rozšíření sekcí 2 a 3. Nová read-only prerequisite + event/read zadání nedokládají připojení živého produceru. Všechny zápisy/deployment nadále host-owned podle AGENTS.md.

### Upřesnění MVP steps/pages kontraktu
Sekce4/5 používají stejný event/store + jeden GET přírůstek jako sekce2/3. Steps/pages nyní vracejí jednotlivé pozorované události v bounded evaluated okně (items/next_token/observed_at, coverage=partial), nikoli úplný nebo latest materializovaný stav všech kroků/stránek. Povinný attempt_no a token obsahující case/document/run/operation/attempt; empty pokračovací stránka je legitimní. Nevyhledávat celou historii k dopárování začátku a konce. PageCompleted/PageFailed jsou jediný terminál stránkového kroku i ve steps, žádný duplicitní StepFinished/StepFailed. Trvání/metoda/model pouze doložené, terminal-only fragment zachovat, nezachycený konec unknown. Cache reuse, artifact-content a totals sem nepatří. Přesný allowlist a navazující worker→HTTP důkaz vymezuje proposal; kontrakt/read dokončení není live producer proof.

### Upřesnění MVP cache reuse a extrakce
Sekce6 rozšiřuje stávající pages/document/run events o PageCacheReused: cached_status completed/failed a známé cached_method/cached_model popisují cache, nikoli nové zpracování/provider call. Sekce7 rozšiřuje existující steps/document/run events o stage=extraction bez page scope a bez obsahu extrakce. Žádné nové endpointy, stored latest stav nebo dvojí completion/Step terminál. Stejný bounded evaluated partial observation-window/cursor/auth/no-store/read503 kontrakt jako sekce4/5. Přesný allowlist a význam viz proposal; contract/read test není živý worker→HTTP proof a nemění požadavek doloženého producer hooku/build/smoke pro celé slices.

### Upřesnění MVP signature/publication/lifecycle
Signature a result_publishing rozšiřují existující Step observations; ResultPublished je oddělený fakt publikovaného result_status/reference, nikoli terminal run. RetryEnqueued/AttemptFinished/RunFinished rozlišují skutečný retry, konec pokusu a runu; max-attempt konec nevyžaduje smyšlený nový claim. Runs/detail/document audit snapshot používají jediný bounded evaluated partial observation window, ne kompletní/latest execution list nebo stored projekci. Konfliktní/late fragments unknown/ambiguous, ne poslední sequence jako business pravda; absence v okně sama neznamená run404/not_instrumented. Case auth/scope a no-store/read503 zachovány. Jediný YAML bude cíleně synchronizován příslušnými read dodávkami; legacy úplné DTO není mandát k neomezenému replay. Celá worker→HTTP dodávka navíc vyžaduje authoritative identity, actual caller/hooks/build a skutečné host runtime evidence, nikoli pouze seeded HTTP fixtures.

### Delivery: skutečný test deployment po každém read přírůstku
Nová read route i rozšíření již existujícího read DTO/allowlistu jsou dokončené až po instalaci, skutečném guarded test deploymentu do existujícího intake App Runneru a přímém live HTTP ověření/doladění agentem v rámci daného zadání, nikoli až závěrečným integračním taskem. Source/TestClient/build ani /health/empty200 nejsou důkaz dodané nové funkcionality. Podrobné safety/recovery/provenance a runtime-inaccessible operator handoff hranice určuje proposal delivery; host pomoc neznamená source-only uzavření. Chybějící actual producer/auth/fixture transparentně blokuje odpovídající live větev, neobcházet identitu/práva ani vyrábět synthetic E2E. Samostatný upload/worker full-path smoke zůstává doplňkovým důkazem, ne náhradou okamžitého read deploymentu.
