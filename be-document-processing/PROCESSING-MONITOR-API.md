# Monitoring dokumentů — rozhraní a pracovní OpenAPI

**Návrh 0.3.0, nikoli implementace nebo nasazené API.**

Strojový kontrakt: [contracts/openapi-processing-monitor.yaml](contracts/openapi-processing-monitor.yaml). Navazuje na [proposal monitoringu](../docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md), zejména části `source-contract`, `monitor-ui`, `read-api`, `instrumentation` a `delivery`. [Rozdíly staršího kódu a AWS](../docs/architecture/document-processing-aws-contract-differences.md) jsou podklad, nikoli příkaz ke změně databáze.

## Autorita a způsob dalšího zpřesňování

**Aktuální AWS business struktura má přednost před checked-in repository adapterem.** Dnešní názvy atributů jsou výchozí mapování, nikoli podmínka budoucí implementace. Zadání agentovi má být po entitách a chování: načti dokumenty případu, metadata uploadu, současnou analýzu, doložený průběh a dostupné artefakty. Agent před implementací znovu ověří aktuální AWS schéma a skutečné API/datové ownery a upraví adapter/kontrakt na potřebný aktuální stav. Nesmí přestavět AWS podle staršího pk/sk/payload kódu ani vymýšlet atributy, aby splnil historický seznam.

Stabilní jsou význam entit, příslušnost k případu/dokumentu, read-only rozsah, bezpečnost a význam nedostupnosti. DTO jsou samostatné projekce nad business daty, nikoli raw DynamoDB dump. Pole mimo identity jsou v business DTO volitelná/nullable; neznámé nové doménové stavy se zobrazí bezpečně jako neznámé, klient zachová původní hodnotu. Nové známé atributy se vystavují až explicitním safe mappingem, ne automaticky přes `additionalProperties` z celé DB. Otevřenost response schémat znamená dopřednou kompatibilitu klienta, ne oprávnění vracet tajná nebo interní pole.

Jde o jeden průběžně upravovaný YAML, ne druhý generovaný kontrakt vedle něj. Během návrhu měnit verzi `0.x`, současně aktualizovat tento průvodce a příslušné sekce proposalu. Před první implementací potvrdit zvolenou revizi; teprve vydané klientské API vyžaduje řízenou zpětnou kompatibilitu. Dnešní chybějící instrumentace nesmí zablokovat návrh nebo read-only pohled nad současnými daty.

## Zápisový model: události, nikoli kopie entit

**Primární auditní zápis je Event.** Dokument, Upload a Analysis jsou read-through pohledy na existující business data; v auditní tabulce se znovu nezakládají. Následující seznam GET endpointů popisuje čtecí DTO, nikoli seznam objektů, které listener musí zapisovat.

- Runtime deník zaznamená převzetí práce, začátek/konec kroku, použití cache, stránkový outcome, publikaci výsledku, skutečný retry a pozorovaný konec pokusu/běhu.
- Každá událost odkazuje na `case_id`, `document_id`, `run_id`, případně `attempt_no`/stage/page. Název, typ, velikost, upload metadata, label, confidence, text a vytěžené hodnoty se **nepřenášejí do auditu**.
- Run/Attempt/Step/Page/AuditSnapshot jsou odvozené runtime pohledy. Základ je event deník, nikoli paralelní sada plných manifestů/snapshotů. Jen pro doložený bounded dotaz lze přidat malý rebuildable runtime index/projekci bez business hodnot. Počet GET endpointů neznamená počet zapisovaných typů.
- Přesná historická reference vstupu/výstupu a minimální tehdejší runtime konfigurace se zachytí jednou u odpovídající události, pokud je nelze bezpečně dohledat z neměnné existující reference. Není to kopie celé business entity ani celého job/config objektu. Mutabilní současná data nenahrazují zaniklou historickou verzi.
- Malá `details` mají allowlist podle typu události. Public Event ukazuje pouze bezpečné opaque artifact ID; interní skutečné reference zůstanou serverové. Nevystavujeme raw event payloady z business objektů.

### První zapisovaná entita k potvrzení: Event

Obálka: `schema_version`, `event_id`, `case_id`, `document_id`, `run_id`, `sequence`, `type`, `occurred_at`, `recorded_at`. Scope podle potřeby: `attempt_no`, `stage`, `page_number`, `correlation_id`.

Payload podle typu:
- `RunQueued`: `job_id` a malý historický runtime kontext/verzovaná reference vstupu; po vytvoření jobu a skutečném enqueue. Není to DocumentCreated ani kopie uploadu.
- `AttemptStarted`: číslo skutečně úspěšně převzatého pokusu; ne neúspěšný claim.
- `StepStarted`/`StepFinished`/`StepFailed`: scope kroku, výsledek, měřené trvání, skutečná metoda/model pokud byly použity, bezpečný error.
- `PageCacheReused`: stránka + reference úspěšně načtené/validované cache; `cache_hit=true`, žádné nové OCR/model call. Metodu/model uloženého výstupu lze připojit z této reference.
- `PageCompleted`/`PageFailed`: runtime outcome, známý fallback/warning/error, měřené trvání a reference potvrzeného mezivýsledku; žádný text/blocks/tables v auditu.
- `ResultPublished`: outcome a reference skutečně publikovaného výsledku; žádná kopie jeho polí nebo textu. Partial publikace může předcházet retry.
- `RetryEnqueued`: úspěšné opětovné předání frontě, známý důvod. Žádný předpokládaný čas budoucího retry.
- `AttemptFinished`/`RunFinished`: zachycený konec odpovídajícího scope a outcome; retry ukončí pokus, ne běh. Chybějící konec se nevymýšlí.

Stejná událost se při opakovaném doručení nemění a nemůže dvakrát přičíst progres. Sequence řadí pozorované události v runu, ne globální causalitu. Absence eventu není důkaz, že business akce neproběhla. Slovník je pracovní a postupně schvalovaný, nikoli již existující producent.

## Rozhraní podle entit (pouze čtení)

Základ: `/v1/cases/{case_id}/processing/documents`. Návrhový prefix `/processing` se nekříží s existujícím ingest/validator `/documents`.

- **Dokumenty** — `GET` základ a `GET /{document_id}`. Union uploadů, analýz a audit-only identit; jeden dokument, odlišená dostupnost každého zdroje. List je kompaktní, detail přidává snapshoty.
- **Upload** — `GET /{document_id}/upload`. Metadata přijetí a reference originálu, žádný nový upload workflow.
- **Analýza** — `GET /{document_id}/analysis`. Aktuální název, popis, klasifikace, stav, počet stran a reference textu, pokud existují. Není to automaticky rich DocumentResult ze source workeru.
- **Auditní projekce** — `GET /{document_id}/audit`. Čerstvost, coverage, aktivní/publikovaný run, aktuální fáze, pokus a počty stran, jen pokud doloženy.
- **Běhy** — `GET /{document_id}/runs`, `GET /{document_id}/runs/{run_id}`. Jeden run = jedno vědomé zpracování, ne každé doručení fronty.
- **Pokusy** — `GET /{document_id}/runs/{run_id}/attempts`. Worker pokusy oddělené od SQS delivery count.
- **Kroky** — `GET /{document_id}/runs/{run_id}/steps?attempt_no=...`. Jednoznačně zvolený pokus, průběh fází a bezpečné chyby.
- **Stránky** — `GET /{document_id}/runs/{run_id}/pages?attempt_no=...`. Provedená native/vision metoda, cache reuse, chyby a reference mezivýsledků; žádné velké přepisy v poll odpovědi.
- **Události** — `GET /{document_id}/runs/{run_id}/events`. Významné přechody, pořadí a čas události versus čas doručení. Žádná syntetická historie ze snapshotu.
- **Artefakty** — `GET /{document_id}/artifacts`, případně `?run_id=...`; `GET /{document_id}/artifacts/{artifact_id}` pro metadata a krátkodobé čtení obsahu. Textové i strukturované mezivýsledky lze iterativně přidávat jako nové typy artefaktů. Samostatné entity vektory/podpisy/field-review se tímto návrhem neduplikují z existujícího validator/review kontraktu.

Všech 13 operací je pouze GET. Nové uploady, retry, cancel, reprocess, korekce a deploy nejsou součást tohoto kontraktu. Auditní čtení obslouží interní package `document_processing/audit/` a existující router stejné služby; žádná nová app, service nebo proces.

## Co lze mapovat z dnešního AWS

### Upload → API Upload
`case_id`, `document_id`, `filename`, `content_type`, `size_bytes`, `sha256`, `received_at`, případně oprávněné `uploaded_by`. Interní `s3_key` se mapuje na opaque `source_artifact_id`, nikoli veřejnou S3 cestu. ID a objekty zůstávají původní.

### Analysis → API Analysis
`case_id`, `document_id`, `title`, `description`, `label`, `label_status`, `confidence`, `page_count`, `processing_status`, `pipeline_version`, `updated_at`. `text_s3_key` se mapuje na `text_artifact_id`. Klasifikační confidence není OCR přesnost. Absence run/attempt, stran či extraction evidence se nepřevádí na smyšlené hodnoty.

### Nový audit → audit/run/attempt/step/page/event
Zapisuje se pouze Event z budoucího listeneru skutečného producenta; audit/run/attempt/step/page jsou jeho čtecí projekce, ne samostatné nové business záznamy. Návrhový YAML nedokazuje jejich uložení nebo nasazení. U legacy dokumentu vrátit `state=unavailable, reason=not_instrumented`, null run reference a neúplnou/neznámou coverage. `updated_at` analýzy není heartbeat ani start/end běhu.

Business stav a auditní stav držet odděleně. Analýza může ukazovat poslední completed výsledek, zatímco audit pozoruje nový processing run; nebo může být audit stale. API nesmí svévolně přepsat business status na základě vedlejšího auditu.

## Revize podle skutečných producentů (0.3.0)

Rozlišení původu: **AWS** = existující business pole doložené průzkumem, **SOURCE** = uložené pouze v checked-in workeru (ne důkaz nasazení), **HOOK** = nový auditní zápis na konkrétní existující hranici. **READ** je serverová projekce, nikoli nové tvrzení o provedení algoritmu. Každá historie HOOK vyžaduje nový append-only event zápis (ne kopii business objektu); nelze ji dopočítat z přepisovaného jobu nebo současné analýzy.

### Existující business pohledy — žádný nový auditní zápis

1. **DocumentSummary / DocumentDetail — identita a složení pohledu (READ)**
   - `case_id`, `document_id`: unie klíčů uploadu, analýzy a případného auditu.
   - `display_name`: neprázdný `analysis.title`, jinak neprázdný `upload.filename`, jinak ID.
   - `relationship`: `matched` (upload+analysis), `upload_only`, `analysis_only`, `audit_only`; computed z potvrzené existence zdrojů, ne z chyby čtení.
   - `processing_status`, `label`, `page_count`, `updated_at`: pouze hodnoty čtené ze současné analysis do odpovědi; v auditu se neukládají; bez ní null/vynecháno. Nejsou stavem posledního auditního pokusu.
   - `audit`: samostatná dostupnost, reference a průběh; legacy `unavailable/not_instrumented` a null runy. Jeho atributy se schvalují v následující skupině entit.
   - Detail přidává `upload` a `analysis`; potvrzeně chybějící snapshot je null, výpadek čtení je chyba.
2. **Upload — metadata přijatého originálu (AWS)**
   - `case_id`, `document_id`; `filename`; `content_type`; `size_bytes` (bajty); `sha256`; `received_at` (UTC); volitelné `uploaded_by` (zdrojový údaj, ne důkaz ověřené identity).
   - `source_artifact_id` (READ): opaque reference nad skutečným `s3_key`, nikoli nový S3 objekt nebo další upload. Přístup k obsahu se autorizuje zvlášť.
   - Konkrétní producent: `be-intake/app/main.py:203–218`, potvrzení zápisu transakcí v následující větvi; hash/identita vznikají před zápisem. Žádný run, start/end uploadu, procenta uploadu ani nový awaiting_upload stav tohoto ingestu.
3. **Analysis — současný business výsledek (AWS)**
   - `case_id`, `document_id`; `title`; `description`; `label`; `label_status`; `confidence`; `processing_status`; `page_count`; `pipeline_version`; `updated_at`.
   - `text_artifact_id` (READ): opaque reference z `text_s3_key`. Bez potvrzeného vztahu k runu nepatří do jeho historických výstupů.
   - Pole doložena existujícím AWS snapshotem a [průzkumem kontraktu](../docs/architecture/document-processing-aws-contract-differences.md#5-výsledek-analýzy--dva-odlišné-modely). Zapisující živý producent této analysis není potvrzen. `confidence` je klasifikační skóre, nikoli přesnost OCR; `updated_at` není dokončení běhu. Pole mimo identity zůstávají volitelná/nullable.

Obálky: `observed_at` (READ čas čtení); jednotlivé business endpointy `state`, `reason`, `data`; kolekce `next_token` (READ cursor). Nic z toho nevyžaduje nový signál z OCR.

### Mapa dalších entit na existující hranice

- **Run** — SOURCE `service.py:99–108`: run/job ID, created_at, source hash/verze, mode/config/config_hash, deklarované pipeline/prompt verze, provider/model/API/region. HOOK po potvrzeném vytvoření jobu a skutečném enqueue emituje `RunQueued`, nikoli kopii jobu/manifest. Lifecycle/status/started/finished se odvodí z událostí claimu a skutečného ukončení/publikace (`pipeline.py:48–55,119–139`). Časy a trvání běhu nelze zaměnit s elapsed posledního pokusu.
- **Attempt** — SOURCE čítač po úspěšném claim update (`pipeline.py:35–54`), nikoli před ním. HOOK emituje `AttemptStarted`, další přechody a konec při `121–139`; retry důvod jen z tam známých error codes. Conflict při claimu není nový pokus. Conflict při práci lze zaznamenat, smrt procesu/lease expiry se sama nehlásí: nedokončený pokus zůstane neznámý, žádné vymyšlené finished_at.
- **Step / Timing / Metrics** — HOOK obalí existující kontrolu zdroje (`66–69`), OCR (`88`), extrakci (`104`) a publish (`119–123`); explicitní start/end/pořadí a monotónní měření. Nové auditní `step_id`, `sequence`, event ID a revision vytváří listener, nejsou business hodnoty. `client_call_duration_ms` lze měřit kolem `BedrockClient.complete`; zahrnuje SDK retries a lokální práci. Pokud wrapper není zapojen nebo hranice nedorazí, měření chybí/null. Počty stran jsou projekce skutečně pozorovaných stavů, ne důkaz kompletní historie.
- **Page** — SOURCE `models.py:89–102`, `pipeline.py:81–98`: existující stránkový výstup s číslem/status/method/model/warnings/error se nekopíruje; API jej může číst přes potvrzenou referenci. Event nese jen fakta o provedení/znovupoužití a reference. HOOK v úspěšné read/validate větvi cache dává `cache_hit`; `PdfFirstOcr.transcribe:40–54` dává známé warning kódy fallbacku. Časování a vazbu na aktuální attempt doplní listener. Failed placeholder s method=vision není důkaz uskutečněného provider volání. U cache metoda/model popisují uložený výstup, ne novou inferenci v aktuálním pokusu.
- **Event / SafeFailure** — HOOK na výše uvedených úspěšných zápisech, známých ProviderError, rozhodnutí requeue a úspěšném `enqueue`. `occurred_at` je čas na hooku, `recorded_at` čas zápisu; sequence je nové auditní pořadí. Nelze garantovat callback po pádu nebo chybu, kterou producent neviděl. `retryable` jen pokud to producent skutečně ví, jinak null. `correlation_id` je nový explicitně předaný technický kontext, ne údaj rekonstruovaný z dokumentu.
- **Artifact** — AWS originál/text, SOURCE preview (`72–80`), cache (`81–92`) a skutečně publikovaný result (`119–123`). READ opaque ID/kind/autorizovaný přístup, HOOK připne známé verze a run/attempt. Velikost/content type/verze jen ze skutečných metadata; hash není ETag a nevzniká domněnkou. Stránkový text/extrakce mohou být autorizovaná projekce potvrzené cache/výsledku, ne předstíraný samostatný uložený soubor. `pending` pouze při skutečně zachyceném záměru. Preview má mutable document/page klíč: bez tehdy zachycené verze se nesmí vydávat za neměnný historický artefakt.
- **AuditSnapshot / Coverage** — READ odvozená projekce runtime událostí (nikoli primární plný snapshot k zápisu): run/attempt/stage, poslední pozorovaná aktivita, známé počty stránek, publikovaný výsledek a revision. `fresh` neprokazuje živost, absence aktivity během volání neprokazuje smrt. `complete` jen při ověřených očekávaných hranicích; mezery a nepozorovaný konec musí být partial/unknown. Bez durable outboxu není záruka bezeztrátovosti.

### Co z revize vypadlo

- `reused_from_run_id`, `reused_from_attempt_no`: cache Page je neobsahuje. `cache_hit` zůstává; původ cache nevymýšlet.
- `input_tokens`, `output_tokens`, cena: `BedrockClient.complete` vrací jen text (`bedrock.py:60–126`), usage nepropaguje. Není to součást tohoto MVP ani rezervovaná metrika bez producenta.
- `queue_wait_ms`: chybí durable čas enqueue pro jednotlivý retry a přesná smlouva co do čekání patří. Bez nové dohodnuté instrumentace se nevrací.
- Periodický heartbeat, přesný okamžik pádu/ztráty lease, plánovaný čas retry a provider request ID: nedoložené signály, ne součást MVP. `last_activity_at` sleduje jen existující hranice.
- Hash promptu/kódu: dnešní verze jsou řetězce deklarované verze, nikoli content hash. Zůstává skutečný `config_hash` a zdrojový SHA-256.
- Embeddingy, podpisové fáze a evaluovaná OCR přesnost bez producenta/ground truth: nepatří do MVP. Přítomné business labely lze číst, ale klasifikační časovou osu z nich zpětně nevytvoříme.

## Návrh obrazovek a jejich napojení

Zůstává existující Wonderful backoffice, ne další aplikace.

```text
Případ → Dokumenty                                      [Obnovit]
Název/ID        Stav analýzy   Dostupnost     Průběh auditu
smlouva.pdf     Zpracováno     upload+analýza Historie není dostupná
scan.pdf        neznámý        jen upload    Historie není dostupná
[po instrumentaci: fáze, hotové/chybné/běžící/zbývající strany]
```

Název řádku: `analysis.title`, jinak `upload.filename`, jinak ID. `relationship` výslovně rozlišuje `matched`, `upload_only`, `analysis_only`, `audit_only`. Aktuální stav filtru znamená **business analysis status**; žádná analýza = unknown. Zvláštní stav pozorování auditu se nezaměňuje za business failed. Summary karty celého případu nejsou odvozeny z jedné stránky seznamu; přesný agregát by potřeboval vlastní rozhodnutý kontrakt/projekci.

Detail má oblasti:
1. **Dokument a analýza** — upload metadata, název, popis, label/confidence/status, dostupný originál/text. Funguje už nad současnými daty.
2. **Průběh** — odvozený audit snapshot + výběr běhu + pokusy + kroky + události. Bez instrumentace vysvětlení nedostupné historie, nikoli prázdný úspěšný timeline.
3. **Stránky a mezivýsledky** — zvolený run a attempt, grid/list stránek, metoda/cache/chyba, odkazy na preview/text/strukturovaný výstup. Cache reuse není nové OCR volání.
4. **Výstupy a diagnostika** — artefakty a bezpečné technické údaje pro povolenou roli. Opravy a validace navazují na stávající samostatný review tok, tento návrh jim nepřidává write API.

První načtení list/detail; ostatní entity načítat až po otevření oblasti. Pollovat jen viditelný aktivní audit přibližně 2–5 s, background pomaleji, backoff/Retry-After při chybách, terminal zastaví běžné pollování, ruční refresh zůstává. Kontrolovat projection_revision proti opožděným odpovědím v rámci téhož dokumentového auditu, ne proti revizi celé business analýzy. Absence instrumentace neznamená spuštění nekonečného polling cyklu.

## Dostupnost, chyby a stránkování

- `observed_at` = čas čtení. `last_activity_at` = doložená aktivita zpracování, může být null. `fresh/stale/unknown` není business status.
- `available` = zdroj/sada je čitelná, může být skutečně prázdná. `absent` = potvrzená absence business snapshotu, jeho `data=null`. `unavailable` = funkce/historie není dostupná, vždy s důvodem. Pro unavailable kolekci `items=[]`, `next_token=null`; UI rozhoduje podle state, ne délky pole.
- Chyba nutného zdroje vrací 503. Nesmí se z ní stát upload_only, prázdný seznam nebo history unavailable. Neznámé identity 404; oprávnění 403 nebo konzistentní bezpečné maskování. Neznámý run/attempt není existující prázdná sada.
- Všechny kolekce mají `limit` a `next_token`, stabilní explicitní pořadí, scope-bound opaque expirovatelný token. Expirace/rozpor scope 400. Nevracet náhodný poslední Dynamo klíč jednoho zdroje jako cursor sjednoceného listu.
- Dokumentový union musí slučovat tři zdroje po case query; vyčerpat/bufferovat každou větev alespoň po emitované ID, deduplikovat a uchovat pozice v tokenu. Při bounded budgetu povolena kratší/prázdná stránka s tokenem. next_token=null až při úplném vyčerpání, ne při nulovém počtu po filtru.
- Není garantován transakční snapshot mezi tabulkami ani mezi stránkami. Nové dokumenty za už přečteným prefixem se objeví až při refresh. Audit/current detail má vlastní revision; nelze jím prohlásit všechny business zdroje za atomicky konzistentní.
- Časové řazení runů potřebuje vhodný bounded access pattern (např. samostatné řazené index entries ve stejné auditní tabulce); prostý lexikografický RUN#UUID klíč časově neřadí. Provedení tohoto indexu je návrhová otázka auditní persistence, ne důvod měnit business tabulku.

## Bezpečnost a ověření před implementací

Server-only credential, autentizovaná proxy a samostatná case/content autorizace; API klíč samotný nestačí pro případová práva. Nevystavovat interní bucket/key, raw provider odpovědi, privátní dokumentové hodnoty v logu nebo download URL do cache. Veškeré odpovědi soukromé `Cache-Control: private, no-store`; artefakt serverem resolve podle identity, ověřit příslušnost i verzi. UI nepouští HTML/instrukce v přepisu.

Acceptance budoucí implementace: fixtures přesných aktuálních AWS shapes a volitelných atributů; unknown nové stavy; union duplicity/analysis-only/audit-only; více stránek/filtry/prázdná stránka s tokenem/expirace; legacy versus skutečně prázdná historie versus výpadek; žádný leak cizího case/artefaktu; partial/retry a staré audit revision; test, že události/projekce neobsahují business atributy ani celé job/config/result objekty; diference stejného business toku s funkčním, vypnutým i selhávajícím auditním sinkem. Žádná migrace/replay/inference jen kvůli testu monitoringu.

Při návrhu se ověřuje YAML/OpenAPI a vazby souborů, nikoli živý endpoint. Tento dokument, YAML a proposal jsou jediný propojený návrh; implementační zadání vzniknou až na potvrzené entity/oblasti.
