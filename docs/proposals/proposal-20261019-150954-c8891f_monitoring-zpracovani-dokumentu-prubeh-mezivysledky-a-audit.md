# Monitoring zpracování dokumentů — průběh, mezivýsledky a audit

## Záměr
Operátor má u dokumentu zjistit **kde právě je, co už vzniklo, co selhalo, co se opakuje a ze kterého běhu pochází zobrazený výsledek**. Ne další log viewer ani druhý scheduler. Rozšíříme existující WonderfulKB backoffice o přehled dokumentů a detail průběhu; audit implementujeme jako interní Python package uvnitř stávající služby `be-document-processing`, bez nové aplikace, root modulu, procesu či deploy jednotky. **Současná business data a jejich úložiště zůstanou přesně jak jsou. Audit ukládá runtime události navázané jejich identifikátory, nikoli kopie dokumentu, uploadu nebo analýzy.** Velké business výsledky zůstávají v existujícím S3, malý append-only runtime deník v odděleném úložišti. Běh, pokus, krok a průběh jsou čtecí pohledy nad událostmi, nikoli nové business entity k samostatnému zapisování. Návrh neautorizuje implementaci, deploy, inference ani zpracování existujících dokumentů.

## 1. Sjednocení zdrojů a identit <!-- section:source-contract -->
### Co skutečně existuje
Zdrojový modul `be-document-processing` má upload → ověření souboru/verze/hash → frontu → stránkový native/vision přepis → samostatnou extrakci a ověření důkazů → výsledek. Ukládá stránkové cache, náhledy, výsledky a audit oprav. Job má běh, pokusy a owner/lease; opakování nemusí vytvořit nový běh. `auto` rozhoduje pro každou stránku zvlášť, `visual` vynucuje vision. Úspěšné stránky se znovu použijí z cache, selhané zůstanou ve výsledku jako selhané. Následná deterministická validace případu porovnává doložené hodnoty napříč dokumenty a je dnes volaná při čtení, nikoli samostatná potvrzená worker stage.

**AWS má odlišný kontrakt než tento adapter.** Existující `wonderfulkb-uw-documents` a `wonderfulkb-uw-document-analysis` mají klíče `(case_id, document_id)`. První eviduje přijetí a S3 originál; druhá aktuální analýzu, štítek, stav, počet stran a odkaz na text. Zdrojový `AwsRepository` očekává `pk/sk/payload/revision` a SAM pro něj definuje jinou tabulku. Nesmí se pouze změnit název tabulky v konfiguraci. Inventura vybraného AWS účtu/regionu neprokázala běžící processing SAM/Lambda/SQS; existující analýzy tedy nelze bez další provenance připsat tomuto workeru.

### Rozhodnutí
- **Aktuální AWS business schéma má přednost před starším kódem komponenty.** Dnešní atributy jsou výchozí evidence, ne zamrazený požadavek na budoucí DB. Zadání implementace formulovat podle entit a chování; agent před prací ověří aktuální strukturu/ownery a přizpůsobí mapování. Žádná migrace AWS do pk/sk/payload jen proto, že to očekává starý adapter. Návrh rozhraní a první read-only pohled lze připravit nad současnými daty bez čekání na finální instrumentaci.
- `case_id + document_id` je společná identita; `document_id` zachovat jako ingest `blob_id`. UI i historie se vážou na tato ID, ne filename ani nový náhodný dokument při monitoringu.
- Upload metadata vlastní ingest, business výsledek vlastní document-analysis. Monitoring nepřepisuje originály, business hodnoty, `confidence`, label ani staré stavy svým odhadem.
- Před instrumentací určit skutečného producenta živých analýz a jeho publish bod; napojit nebo explicitně adaptovat zdrojový modul. Jeden processing owner, žádný druhý nezávislý OCR pipeline pro dashboard.
- Pro list dokumentů případu udělat serverovou sjednocenou projekci obou tabulek. Zobrazit i `upload_only`, `analysis_only` a chybějící telemetry/provenance. Jde o dostupnost vztahu, ne automatické označení dokumentu za vadný. Rozpor se nesmí zamaskovat inner joinem.
- Legacy výsledek bez běhu zobrazit jako „Výsledek dostupný; historie zpracování není k dispozici“. Nevymýšlet run ID, jednotlivé události ani doby zpracování z `updated_at`.
- Pokud worker nadále potřebuje svůj pk/sk runtime store, je to samostatný owner-managed backend. Není totéž co audit ani existující analysis tabulka. Náprava kontraktu komponenty vůči současným business datům je oddělená změna, nikoli migrace schovaná do auditu; audit jejich formát ani publishing nemění. Podrobný soupis je v [rozdílech AWS a komponenty](../architecture/document-processing-aws-contract-differences.md).

**Acceptance:** mapování upload ↔ document ↔ job ↔ run ↔ publikovaný výsledek je doložené; existující tabulky/konzumenti zachováni; žádná domněnka source=deployed. Historický důkaz je v doprovodném AWS checkpointu, ne provozní dashboard data.

## 2. Uživatelské rozhraní <!-- section:monitor-ui -->
### Přehled dokumentů případu — MVP
Rozšířit `apps/backoffice/app/src/documents/CaseDocuments.tsx`, nikoli vytvořit druhou aplikaci. Seznam: název/ID, dostupnost uploadu/analýzy, celkový stav, aktuální fáze, **hotové/selhané/zbývající strany**, pokus, doložený stav zařazení (bez nedoložené doby čekání), délka běhu a čas poslední skutečné aktivity. Filtry: stav, fáze, chyby, vyžaduje kontrolu; summary karty čeká / běží / částečné / selhalo / hotovo.

Příklad řádku: `Dokument A · Zpracovává se · OCR 7/12 stran, 1 chyba · pokus 2 · aktivita před 8 s`. `7/12 OCR` neznamená 58 % celé pipeline: extrakce ještě nemusí začít. Žádné smyšlené procento end-to-end.

Konkrétní návrh oblastí obrazovky a jejich napojení na entity je v [průvodci rozhraním](../../be-document-processing/PROCESSING-MONITOR-API.md#návrh-obrazovek-a-jejich-napojení). První oblast Dokument/analýza používá dnešní business metadata; Průběh, Stránky a Diagnostika přibývají podle skutečné instrumentace. Výsledek jedné stránky listu neslouží jako globální počet pro summary karty.

### Detail dokumentu
- **Souhrn:** stav zpracování, observation freshness, zvolený běh, zdrojová verze/hash, aktuální fáze, první/poslední aktivita, důvod retry, aktuální versus poslední publikovaný výsledek.
- **Průběh a pokusy:** výběr run → attempt, časová osa významných přechodů a fáze s trváním. Retry může vrátit dokument do queued, ale předchozí partial výsledek zůstává dostupný s jednoznačnou provenancí.
- **Stránky:** mřížka 1…N, completed/failed/not_started/running, native/vision, důvod fallbacku, cache-hit versus skutečně provedeno, model, trvání, kód chyby; proklik na preview a dostupný přepis i před finálním výsledkem.
- **Vytěžené údaje a důkazy:** navázat na `DocumentReview.tsx`, raw/normalized hodnota, role, stav extracted/not_found/unreadable/ambiguous/human_corrected, zdrojová strana/blok/citace, původní vs opravená hodnota.
- **Výstupy:** originál, preview, stránkový přepis, finální JSON/text, verze/provenance a dostupnost. Rozlišit „není vytvořeno“, „nepodařilo se načíst“, „nemáš oprávnění“ a prázdný platný výsledek.
- **Diagnostika:** kódy chyb, retryability, model/API/region, pipeline/prompt verze, pokusy a znovupoužití cache. Interní technické detaily jen oprávněné roli.
- **Kontroly případu:** existující výsledky s odkazy na konkrétní run/opravy; oddělit `issues_found`, `incomplete`, `consistent` a nenastavený completeness profil. Soulad neprokazuje pravost.

MVP je read-only monitoring; existující ruční korekce se zachovají se samostatným oprávněním. Nové Retry/Cancel/Reprocess ovládání není součástí návrhu první verze.

**Acceptance:** prázdný případ, legacy analýza, upload bez analýzy, live progress, částečný výsledek při retry, dokončeno s varováním, nedostupné telemetry a selhaná stránka mají odlišný a srozumitelný UI stav; desktop i užší obrazovka, ovladatelnost klávesnicí, žádné spoléhání pouze na barvu.

## 3. Fáze, sledované hodnoty a jejich význam <!-- section:signals -->
### Hranice fází
Pracovní slovník oblastí, nikoli garantované lineární pořadí: `source_validation`, `queued`, `page_transcription`, `extraction`, `result_publishing`, `terminal`. Přijetí uploadu už eviduje business ingest a nekopíruje se jako auditní dokumentový snapshot. Skutečný časový sled určují zachycené události, včetně opakovaného ověření zdroje při pokusu.

V rámci stránky: `preview`, `native_text_assessment`, `native_transcription` nebo `vision_transcription`, `page_cache`. Volba `auto/visual` je konfigurace, native/vision skutečně provedená cesta. Nepřidávat uživateli umělé worker jobs pro každou dílčí funkci.

Klasifikace labelu/popisu, text/image embeddingy a podpisy mají záznam capability/stage pouze pokud jejich producent existuje. Návrhový validator-agent kontrakt a S3 Vectors nejsou důkazem, že tyto fáze dnes probíhají v tomto workeru. `not_instrumented`, `not_configured`, `skipped`, `pending` a „úspěch s nulovým počtem nálezů“ jsou různé věci.

### Kontrola naplnitelnosti — revize 0.3.0
Každý atribut musí mít konkrétního producenta: existující AWS business pole, existující SOURCE hodnota workeru, nový runtime event z HOOK na skutečné hranici nebo deterministická READ projekce. AWS/SOURCE business hodnoty se při čtení připojí z jejich vlastníka, nekopírují se do auditního deníku. Historický runtime kontext je výjimka pouze v minimálním rozsahu nutném k doložení konkrétního běhu. [Průvodce](../../be-document-processing/PROCESSING-MONITOR-API.md#revize-podle-skutečných-producentů-030) uvádí mapu všech entit na konkrétní zdrojové body a oddělení čtecích business pohledů od první zapisované entity Event. SOURCE není důkaz nasazení. Nové auditní ID/sequence/revision a časování vytváří auditní listener, ale business chování nemění; nezachycenou událost nesmí zpětně vymyslet.

Z kontraktu odstraněny původní run/attempt cache, tokeny, cena a queue wait; pravidelný heartbeat ani hash kódu/promptu nejsou součást scope. Cache hit a důvod fallbacku zůstávají jen z konkrétních větví. Preview/result/cache artifact nemá historickou neměnnost bez potvrzené verze/provenance. Detailní soupis v průvodci má přednost před obecnými ilustracemi.

### Co číst dnes vs co přidat
- **Přijetí a identita — dnes:** case/document, typ/velikost souboru, received_at, hash/S3 reference; v source workeru page_count a neměnná source_version. **Doplnit:** `RunQueued` s identitami a minimální historickou referencí na použitou verzi vstupu; nikoli kopii ingest objektu nebo jeho metadata.
- **Fronta a worker — část dnes:** job.status, attempts, owner a lease, created_at. **Doplnit:** auditní claim/start/finish/requeue časy na existujících hranicích a známý retry error code. Periodický heartbeat a `queue_wait_ms` nejsou součást MVP; chybí per-attempt enqueue evidence.
- **Stránky — dnes:** cache Page s method/model/text/blocks/tables/visual_marks/warnings/error; fallback reason je ve warnings. **Doplnit:** průběžnou dostupnost přes API, started/finished/duration a cache_hit z úspěšné cache read/validate větve. Cache neobsahuje původní run/attempt: source_attempt reference se nevrací; retry count patří k pokusu, ne k neexistující stránkové historii. Žádné další LLM volání kvůli dashboardu.
- **Extrakce — dnes:** typ dokumentu, fields, normalizace, citace, model, warnings, evidence validation. **Doplnit:** runtime start/end extrakce a měřené trvání. Hodnoty, citace, stav i počty polí číst z existujícího autorizovaného výsledku; neukládat je do auditu. Nedělit počtem všech možných fields jako údajnou úplností.
- **Výsledek a audit — dnes:** result JSON s run/attempt/config/elapsed/completed_at a oddělené korekce; živá analysis má zploštěný snapshot. **Doplnit:** `ResultPublished` s referencí na skutečný výstup/verzi a outcome; historii běhů/pokusů tvoří runtime události. Žádná kopie výsledku nebo nové auditní analysis záznamy.
- **Spolehlivost — doplnit:** pozorované first/last error, kód, fáze/stránka, známé retryable a uskutečněné requeue. Neznámý pád/ztrátu lease nebo plánovaný čas retry nelze hlásit jako zachycenou událost; chybějící konec zůstane unknown. Freshness je stáří poslední zachycené hranice, ne důkaz živosti. SQS delivery count je jiná metrika než počet worker pokusů; globální DLQ/queue age jsou agregované AWS metriky, ne stav jednotlivého dokumentu.
- **Latence — dnes:** výsledkové elapsed_seconds pokusu a konfigurace. **Doplnit hookem:** stage duration a `client_call_duration_ms` kolem existujícího `BedrockClient.complete`; to zahrnuje lokální práci/SDK retries, nikoli čistou provider latency. **Vyřazeno:** tokeny a cena; klient vrací jen text a usage nepropaguje. Bez instrumentovaného měření chybí hodnota/null, nikoli nula.
- **Kvalita:** VLM OCR bbox/confidence mohou být null, to je platné. Živé `confidence` je dle kontraktu klasifikační skóre, ne kalibrovaná OCR přesnost. CER/WER jen proti anotovaným evaluacím, ne „přesnost živého dokumentu“ bez reference. Podpis/razítko ani semantic consistency nejsou ověření pravosti.

ProcessingStatus zůstává `awaiting_upload|queued|processing|completed|partial|failed`. `stale` je samostatné pozorování freshness, nikoli automatická změna na failed. Stav kroku: `pending|running|succeeded|failed|skipped`; absence coverage/instrumentace je samostatný atribut.

**Acceptance:** slovník metrik uvádí jednotky, zdroj a null semantics; chybějící signál se nevydává za nulu nebo úspěch.

## 4. Datová struktura a ukládání <!-- section:data-model -->
### Co zapisujeme a co pouze čteme
1. **`wonderfulkb-uw-documents`:** jediný vlastník originálu a ingest metadata. Název, MIME, velikost, upload čas, uploadér a současný hash/odkaz se čtou odsud. Audit nekopíruje Upload ani Document.
2. **`wonderfulkb-uw-document-analysis`:** jediný vlastník současného business výsledku; zachovat klíče, pole, význam i publishing. Název/popisek, label, confidence, business status, počet stran, hodnoty a textové odkazy čteme odsud nebo z existujícího výsledku. Audit sem nepřidává žádná pole a nevytváří druhý Analysis snapshot.
3. **Nová úzká tabulka `wonderfulkb-uw-document-processing-audit`:** append-only runtime **Event**. Běh/pokus/krok/stránkový průběh jsou projekce těchto událostí. Nezapisujeme zvlášť business entity a pak ještě událost o jejich kopii. Runtime job/lease store je nadále výhradním execution ownerem, není auditní autoritou.
4. **S3:** business obsahy/cache/preview/výsledky mají dosavadní cesty a lifecycle. Události obsahují pouze bezpečné interní reference na skutečně potvrzený objekt/verzi. Žádný nový auditní manifest kopírující dokument, job, konfiguraci nebo výsledek. Velké obsahy se neukládají do auditu; presigned URL se tvoří až při autorizovaném čtení.

### Jediná primární zapisovaná entita: Event
Povinná obálka: `schema_version`, `event_id`, `case_id`, `document_id`, `run_id`, `sequence`, `type`, `occurred_at`, `recorded_at`. Volitelný scope: `attempt_no`, `stage`, `page_number`, `correlation_id`. Timestamp hooku je jiný než čas uložení; pořadí je uvnitř runu, nikoli globální causalita.

Payload má jen fakta příslušného runtime přechodu: outcome, změřené trvání, skutečně použitou cestu/model, úspěšné použití cache, známý fallback/warning code, bezpečný error a reference vytvořených/použitých artefaktů. Žádný název souboru, titul/popisek, MIME, velikost, uploadér, label/confidence, vytěžené hodnoty, přepis či raw provider request/response. Text chyby je mapovaný bezpečný popis kódu, nikoli libovolná výjimka s dokumentovým obsahem.

**Historický kontext běhu:** `RunQueued` může jednou zachytit `job_id`, `config_hash`, deklarované pipeline/prompt verze, režim, provider/API/region a konfigurované OCR/extraction modely, pokud nejsou dostupné přes neměnnou referenci. Reference zdroje zahrne skutečnou verzi nebo známý hash pouze pokud samotné ID dokumentu nedokládá použitý vstup. Preferovat existující neměnnou referenci; nekopírovat celý job/config/source objekt. Jde o důkaz „s čím tento běh skutečně začal“, ne druhou autoritu pro aktuální data. Další události tento kontext neopakují. Pokud ref chybí nebo zanikne, historický obsah zůstane unavailable, nepodstrčí se aktuální objekt.

Příklad zapisované runtime události (syntetický, ne business snapshot):
```json
{
  "schema_version": "1.0",
  "event_id": "evt-demo-7", "case_id": "c-demo", "document_id": "d-demo",
  "run_id": "r-demo", "attempt_no": 2, "sequence": 7,
  "type": "PageCacheReused", "stage": "page_transcription", "page_number": 1,
  "occurred_at": "2026-10-19T15:00:00Z", "recorded_at": "2026-10-19T15:00:00.020Z",
  "artifact_ids": ["cache-page-demo"],
  "details": {"cache_hit": true, "outcome": "completed"}
}
```

### Minimální slovník událostí a skutečné hranice
- `RunQueued`: po potvrzeném vytvoření jobu a úspěšném předání enqueue (`service.py:99–123`). Konflikt/existující job nesmí založit nový run; případné další skutečné předání má vlastní `RetryEnqueued`/delivery identitu.
- `AttemptStarted`: jen po úspěšném claimu s inkrementovaným attempts (`pipeline.py:35–54`). Conflict při claimu není pokus.
- `StepStarted`, `StepFinished`, `StepFailed`: skutečné hranice ověření zdroje, OCR/extrakce a publikace, nikoli imaginární stage. Page scope použít u stránky; neběží druhý stránkový scheduler.
- `PageCacheReused`: až po úspěšném čtení a validaci cache (`81–84`). Není nová inference. Metodu/model lze při čtení připojit z odkazované cache; nepředstírat původní run/attempt.
- `PageCompleted`, `PageFailed`: outcome skutečného pokusu o stránku a potvrzená reference výstupu. Warning/fallback jen z existujících kódů, failed placeholder nedokazuje model call.
- `ResultPublished`: až po existujícím úspěšném publish bodu (`119–123`), nikoli už po samotném zápisu JSON do S3. Outcome a reference výstupu; žádné kopírování analýzy. Publikace partial nemusí znamenat terminální konec runu.
- `RetryEnqueued`: po skutečném úspěšném enqueue (`125–139`), ne příslib budoucího retry. Error/retry reason, pouze pokud producent skutečně zná.
- `AttemptFinished`, `RunFinished`: pouze při pozorovaném konci příslušného scope. Při retry může skončit attempt, ale ne run. Pád/nezachycený konec zůstává unknown; max-attempt větev může doložit `RunFinished` bez vymyšleného nového attempt.

Přesný allowlist payloadu pro každý typ musí být před implementací potvrzen. Public Event jej v návrhu zpřístupňuje typovanými malými details; ne raw business object ani obecné metadata pole.

### Persistence a access patterns
Základ deníku: `pk = CASE#<case_id>#DOC#<document_id>#RUN#<run_id>`, `sk = EVENT#<ordered_sequence>#<event_id>`. Immutable put s idempotencí podle event identity; repeat doručení uloženou událost nemění. Pořadí nesmí být obyčejné UUID ani samotný wall-clock. Přidělování sequence/fencing musí mít explicitní souběhový a gap kontrakt; selhání auditu nesmí blokovat business publish.

Řazení běhů a case audit-only identity řeší sparse indexy přímo nad `RunQueued` (document/time/run a case/document/run), nikoli nové dokumentové kopie. Případný run s chybějícím úvodním eventem musí být dohledatelný jako partial: přímý run lookup a index membership z ostatních událostí, nebo malý odvozený runtime index bez business polí. Konkrétní bounded návrh ověřit před implementací; sparse index pouze na chybějícím RunQueued by takový běh skryl.

API `Run`, `Attempt`, `Step`, `Page`, `AuditSnapshot` jsou **čtecí DTO**, ne automatický seznam DynamoDB itemů. MVP nevyžaduje současně CURRENT + RUN/META + ATTEMPT/META + STEP + kopii Event. Výchozí je event deník; pokud bounded polling/listing vyžaduje materializaci, povolit jen minimální odvoditelný runtime index/projekci s doloženým dotazem a cenou. Obsahuje ID/event cursor a stav z událostí, žádné business atributy, celé config objekty nebo výsledky. Takovou projekci lze obnovit z dochovaných událostí bez business replay/inference; mezery tím nezmizí. Čtení nesmí při každém pollu bez limitu přehrávat celou historii.

Case view = paginované čtení business upload + analysis + auditních identit, join na serveru podle case/document. Historické stránky/artefakty se připojují jen z potvrzené reference eventu; současný business obsah se nesmí vydávat za obsah tehdejšího běhu. Žádný Scan celé tabulky na refresh, žádný horký globální status index pro MVP.

**Acceptance:** auditní zápisy jsou pouze allowlistované runtime události a nezbytné odvoditelné runtime indexy. Testy ověří absenci business atributů/obsahů, idempotenci, bounded query, čitelnost mezer, historické reference a oddělení aktuálního business pohledu od časové osy. Žádná změna business schématu nebo kopírování business entit.

## 5. Interní auditní package, zápis a obnova <!-- section:instrumentation -->
### Izolace implementace
Umístění: **`be-document-processing/src/document_processing/audit/`**, interní package stejné služby, ne nový kořenový modul nebo samostatná knihovna/service. Audit má vlastní event kontrakt, listenery, storage adapter a query/projection logiku. Business pipeline nesmí importovat boto3 pro audit, sestavovat DynamoDB itemy či S3 klíče auditu, nastavovat jeho retenci ani obsahovat jeho retry/catch bloky.

Návrhové rozdělení (soubory jsou návrh, ne existující implementace):
- `events.py` — typované immutable události a malý `AuditListener`/`AuditSink` protokol; explicitní correlation/run/attempt/page context.
- `listener.py` — konkrétní listener, bezpečná serializace/redakce, idempotence, fencing auditní projekce, skládání read modelu a izolace chyb.
- `storage.py` — append-only DynamoDB deník a jen odůvodněné odvoditelné runtime indexy; žádný zápis do business tabulek ani nový business manifest.
- `queries.py` — stránkované auditní čtení a DTO; stávající HTTP router jen deleguje, nezavádí novou aplikaci.
- `instrumentation.py` — úzké wrappery/dekorátory/context managers pro měření a start/finish/failure události, pokud skutečně zjednoduší kód; `NoOpAudit` pro vypnutí a testy.
- `__init__.py` — malé stabilní veřejné rozhraní a factory pro zapojení v existujícím composition rootu. Nevytvářet plugin registry ani obecný event bus.

Preferovat **jeden injektovaný listener** s explicitními sémantickými událostmi (`RunQueued`, `AttemptStarted`, `StepStarted`, `StepFinished`, `PageCacheReused`, `PageCompleted`, `PageFailed`, `ResultPublished`, `RetryEnqueued`, `AttemptFinished`, `RunFinished`); přesné názvy/kontrakt stanoví implementační návrh. V hlavním toku jen vytvoření události s hodnotami, které už zná, a předání přes malé rozhraní. Událost po business zápisu říká, že zápis skutečně uspěl, ne jen že byl zamýšlen. Dekorátor sám nestačí pro cache-hit, partial či ztrátu lease; tyto sémantické body musí být explicitní. Žádné monkey-patching, globální mutable context nebo rozesílání kopie všech dokumentových hodnot do auditu.

Zapojení závislostí: `composition root → business service/worker + audit listener`; `business → malý event protokol`; `audit → vlastní persistence`. Audit nevolá zpět business kroky ani si nečte jeho interní mutable objekty. Čtecí server-side projekce může spojit business a audit data, ale nevytváří tím novou business autoritu.

### Provozní pravidla
- Instrumentovat existující hranice `complete_upload`, claim, stránkový cache hit/OCR, extrakce, publish a retry. Veškeré chování navíc držet v package výše, nikoli rozprostřené po `pipeline.py`, `service.py`, `bedrock.py`. Nevytvářet druhý worker, globální tracing platformu nebo přepis algoritmu jen pro monitoring.
- Runtime job/lease zůstává jedinou autoritou pro exekuci. Telemetry je projekce runtime událostí; business výsledky se čtou od jejich vlastníka. Audit nesmí sám spouštět retry ani rozhodovat o ukončení práce.
- Event idempotency key odvozovat z run/attempt/stage/page/transition; retry doručení nesmí přičíst completed stránky dvakrát. Run/attempt fencing a monotónní revision chrání CURRENT před starým workerem; cache hit eviduje úspěšné použití konkrétního cache artefaktu, netvrdí novou OCR inferenci ani původní run/attempt, který cache dnes neukládá.
- **Žádná společná audit+business transakce jako nová podmínka business úspěchu.** Existující publishing, owner/lease ochrany i transakce se auditem nemění. Listener dostane `ResultPublished` až po úspěšném existujícím publish bodu a ukládá samostatný auditní záznam. Je-li producent externí, potřebujeme jeho explicitní událost/adaptaci, ne odhad stavu z auditní tabulky.
- Audit referencuje pouze již potvrzené business artefakty a zachovává jejich originální cesty/verze. Auditní zápis obsahuje malou referenci události, ne nový manifest kopírující tyto business objekty; retence se týká jen auditního deníku/indexů. Nemění tím lifecycle business souborů.
- Chyby auditu zachytává auditní adapter (ne business funkce); nesmí změnit business návratovou hodnotu, výjimku, retry, lease ani stav výsledku. Zápis má omezený timeout/retry budget, žádné neomezené čekání nebo frontu v paměti. Při nedoručení bezpečný strukturovaný fallback log se stejným event_id a samostatná diagnostika. UI musí přiznat stale/unknown či neúplnou historii; při úplném výpadku sinku nelze slibovat, že se v DB objeví i příznak chyby. Další platná událost může obnovit snapshot, ne zpětně vymyslet chybějící historii.
- Přiznaná garance: interní listener bez durable outboxu nemůže současně zaručit audit každé události při pádu procesu a nulový dopad na business cestu. MVP je fail-open provozní audit s detekovatelnými mezerami, nikoli neztratitelný regulatorní ledger. Pokud bude povinná úplnost, vyžaduje samostatné rozhodnutí o durable delivery nad existujícími commit událostmi; nesmí se potichu přidat business pole/outbox do současných dat nebo nový service.
- V MVP žádný nový periodický heartbeat/timer. `last_activity_at` se mění jen na zachycených existujících hranicích (claim, stránka, extrakce, publish/requeue). Start volání může ukázat čekání/age, ale absence další události nedokazuje mrtvého workeru ani přesný okamžik ztráty lease. Freshness pravidla musí přiznat toto omezení.
- Ukládat UTC časy a monotónně měřená trvání; součet provider latencí a wall-clock trvání nejsou vždy totéž. Žádné odvozování historie z pořadí příchodu poll odpovědí.
- Žádný legacy backfill kopírující existující business metadata. Při čtení se zobrazí `history_available=false`/not_instrumented; bez runtime eventů nevytvářet historické události ani běhy a nepřepočítávat inference.

**Acceptance:** testy duplicitního doručení, přerušení po artefaktu, souběhu starého/nového workeru, cache retry, chybějící telemetry a změny konfigurace. Navíc differential test stejného syntetického business toku s `NoOpAudit`, funkčním listenerem a selhávajícím sinkem: stejné business writes, výstupy, chyby, retry a identita dokumentu, žádná auditní pole v business datech. Zkontrolovat směr importů: storage/serialization/retry auditu pouze v `audit/`; event hook až po potvrzení příslušné akce. Původní postup fencing a idempotence se nesmí oslabit.

## 6. Čtecí API a zabezpečení <!-- section:read-api -->
**Pracovní strojový kontrakt:** [OpenAPI YAML](../../be-document-processing/contracts/openapi-processing-monitor.yaml), **verze 0.3.0 — návrh, ne nasazené API**. [Průvodce a mapování entit](../../be-document-processing/PROCESSING-MONITOR-API.md) je uložený u stejné komponenty. Tyto soubory postupně upravovat společně s touto sekcí; názvy atributů nad dnešním AWS lze před implementací zpřesnit, entity/ownership a read-only hranice zachovat. Není potřeba nový modul ani nová služba.

Case-scoped kontrakt má 13 GET operací pod `/v1/cases/{case_id}/processing/documents` (nekoliduje s ingest/validator `GET documents`):
- základní list a `/{document_id}` — sjednocená identita + oddělené business a audit snapshoty; union všech zdrojů.
- `/{document_id}/upload` a `/analysis` — read-through dnešní business entity, **žádné nové auditní zápisy** a žádné vynucení source DocumentResult.
- `/{document_id}/audit` — aktuální pozorování a coverage, legacy explicitně unavailable.
- `/{document_id}/runs` a `/runs/{run_id}` — paginované běhy a jeden pohled běhu doložený událostmi a minimálním historickým kontextem.
- `.../runs/{run_id}/attempts`, `/steps?attempt_no=...`, `/pages?attempt_no=...`, `/events` — oddělené pokusy, fáze, stránkové mezivýsledky a časová osa. Pokus je pro kroky/stránky povinný, ne implicitně poslední.
- `/{document_id}/artifacts?run_id=...` a `/artifacts/{artifact_id}` — stránkované dostupné výstupy a autorizované krátkodobé čtení obsahu. Legacy text se nesmí vydávat za výsledek libovolného historického běhu.

Stránkování sjednoceno jako `limit` + `next_token`, filtr listu `processing_status` je **business analysis status**, nikoli odhad z auditu. Řazení dokumentů document_id; merge token zachovává pozice/buffer všech zdrojů a scope/filtry/expiraci. I kratší či prázdná stránka může mít next_token; null znamená vyčerpání všech zdrojů. Není garantován transakční snapshot mezi tabulkami/stránkami. Detail přiznává current business status zvlášť od auditního processing statusu.

Dnešní atributy kromě identity nejsou v business DTO povinné, nové neznámé doménové statusy nesmí shodit klienta. Žádný raw DynamoDB dump; nové pole vyžaduje vědomé safe mapping rozhodnutí. Kolekce vrací availability a coverage: unavailable/not_instrumented není pozorovaná prázdná historie. Výpadek nutného zdroje je 503, ne úspěšný prázdný výsledek.

Response obsahuje `observed_at`, u auditu nullable `projection_revision`, `freshness`, availability/coverage a jednoznačné null/absence semantics dle YAML. `observed_at` není heartbeat; revision není společná business transakce. 404 neexistující identita, 403 nepovolený přístup, nedokončený artifact explicitně pending; chyba čtení nesmí změnit seznam na prázdný. GSI eventual consistency přiznat; vybraný CURRENT/detail číst strong z primárního klíče a starší revision nesmí přepsat novější UI.

Použít existující `createDocumentApi` a server proxy, **API klíč nikdy do browser bundle**. UI poll 2–5 s jen při aktivním processing a viditelné stránce, pomaleji při backgroundu, backoff/Retry-After na 429/chybách, stop po terminal; ruční refresh. SSE/WebSocket nejsou nutné pro MVP. Nesdílet credentials/runtime s Mission Control; proposal se tam sleduje jako práce, dokumentová data zůstávají WonderfulKB.

Všechny odpovědi `Cache-Control: private, no-store`; serverový API klíč sám není případová autorizace — existující autentizovaná proxy/server musí ověřit oprávnění ke case i zvlášť k obsahu artefaktů. Zachovat region eu-central-1 a case-scoped oprávnění; v telemetry jen safe error messages a technické identifikátory, nikoli plné prompty, citlivé dokumentové hodnoty či odpovědi providera. Čtení obsahu a korekce oddělená oprávnění; browser renderuje nedůvěryhodný text bez spouštění HTML/instrukcí. Retence návrhově: runtime event deník 30 dní, odvoditelné indexy/projekce nesmějí předstírat historii po smazání zdrojových eventů; skutečnou dobu a audit povinnosti musí potvrdit vlastník dat. TTL nesmí smazat jediný audit korekcí ani business výsledek.

**Acceptance:** contract tests pagination/nullability/error states, izolace případů, auth k artefaktům a redakce chyb; UI se zastaví na terminal a nezamění API chybu za úspěšný prázdný výsledek.

## 7. Realizace a ověření <!-- section:delivery -->
Doporučené vertikální kroky po schválení návrhu:
1. **Read-only přehled existujícího stavu:** identity/source adapter, paginovaný case list a detail; živá analysis se zobrazuje poctivě jako legacy bez historie. Sjednotit rozhodnutí o processing producerovi a jeho napojení; žádný automatický deploy/source cutover.
2. **Jeden průchod s průběhem:** interní `document_processing/audit/` package + jeho samostatné schema/listener/storage + malé event hooks skutečného producenta + read API + timeline/page progress v existujícím UI v jedné ověřitelné vertikále. Business kontrakt ani data neměnit; žádný nový app/root modul/proces. Nezavádět tabulku bez skutečného zapisovatele/čtenáře.
3. **Pokusy a mezivýsledky:** cache reuse events, retry/partial event history a reference existujících artefaktů, fencing a recovery testy, provázání existující review/korekce/validace.
4. **Diagnostika:** skutečně instrumentovaná stage/client-call trvání a bezpečné chyby. Usage/cena, queue wait, periodický heartbeat, cache origin, embedding/signature fáze a globální ops pohled nejsou MVP. Případné rozšíření až se samostatně doloženým producentem a schváleným kontraktem.

Testovat hermeticky na syntetických PDF/stránkách a AWS adapter fixtures: native-only, mixed/vision fallback, vypršený lease, provider timeout, chybné JSON, failed page, partial+retry, duplicita, legacy/missing references a unknown metrics. UI: filtry, běh/pokus, dostupný mezivýsledek, proklik evidence, přístupnost, stale refresh a mobilní šířka. E2E provede celý tok syntetického dokumentu v izolovaném prostředí bez skutečné inference. Samostatně ověřit na schváleném cloud nasazení metadata → progress → artefakt → terminal provenance; source/test pass není důkaz nasazení.

Měřit query počty/velikost odpovědi a write amplification na dokument/stranu; načtení case nesmí scanovat celé tabulky, auto-refresh nesmí stahovat OCR text. UI přijetí doložit screenshoty skutečných syntetických stavů. Registrace implementačních tasků až po schválení scope; tímto proposalem se žádný worker ani cloud prostředek nespouští.

## Podklady a otevřená rozhodnutí
Zdrojové reference: `be-document-processing/src/document_processing/pipeline.py:27–148`, `service.py:52–154`, `repository.py:64–116`, `pdf_first.py:9–54`, `models.py:89–103,142–223`; `be-document-processing/template.yaml:71–90`; `VALIDATOR-AGENT.md` (kontrakt, ne potvrzená implementace); existující `CaseDocuments.tsx`, `DocumentReview.tsx`, `createDocumentApi.ts` v backoffice.

Hostitelské evidence checkpointy (bez dokumentových obsahů a tajemství):
- `knowledge/projects/wonderfulkb-processing-monitor-source-20261019.md`
- `knowledge/projects/wonderfulkb-processing-monitor-aws-20261019.md`
Tyto cesty jsou v OpenClaw workspace, ne v aplikačním repozitáři. Číselné inventurní pozorování a použité read-only AWS operace jsou v checkpointu; runtime počty nejsou specifikace.

Před implementací vyjasnit především **který producent dnes zapisuje živou analýzu a zda ho integrujeme, nebo vědomě nahrazujeme/adaptujeme**. Další rozhodnutí: identity/role provozních uživatelů, retence/audit a požadovaný provozní rozsah mimo konkrétní případ. Výchozí návrh je case-centric monitoring v existujícím backoffice, bez nových řídicích akcí a bez předstírání chybějící historie.
