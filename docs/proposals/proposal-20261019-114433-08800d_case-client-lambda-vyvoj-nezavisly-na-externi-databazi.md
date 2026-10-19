# Case & Client Lambda — nejdřív mock, potom externí databáze

## Záměr a změna rozsahu <!-- section:context type:context -->

Zdroj: `plans/case-client-aws.md`, HTTP rozhraní: `be-case-client/openapi-case-client.yaml` (1.3.0-final). Zadání: co nejjednodušší funkční Lambda, nejdřív nasaditelná se syntetickými daty bez databáze; skutečnou DB dodá jiný vlastník a připojí se později. Tento dvoufázový rozsah nahrazuje původní čtyři balíčky tohoto proposalu. Zdrojový plán není přepsán a jeho kroky pro DynamoDB nejsou součástí první fáze.

Dvě části:
1. Jedna Lambda + mock repository, lokální testy, minimální SAM šablona a připravený postup nasazení/smoke bez DB.
2. Nahradit mock repository skutečným adaptérem a ověřit tutéž službu proti externí DB.

První část má jeden implementační task: `plans/tasks/2026-10-19_case-client-lambda-mock.md`. Host vlastní instalaci nástrojů, konfiguraci projektového test runneru a skutečné nasazení; implementační task dodává kód a nasaditelné artefakty, neprovádí cloudové změny. Tvorba návrhu/task briefu sama nespouští implementaci ani AWS deploy. Autocommit zůstává vypnutý.

### Jedno zadání až po ověřený cloudový výsledek

Uživatelský požadavek 19. 10. 2026 14:28 zahrnuje **implementaci → nezávislou kontrolu a lokální testy → host deploy → skutečné HTTP integrační testy**, bez nutnosti nového obecného zadání po dodání kódu. Kód adaptéru a integračního runneru patří implementačnímu agentovi; instalace, AWS konfigurace, deploy a živé ověření hostovi. Nejde o předání SSO/produkčních oprávnění repo-scoped agentovi ani o další coding task. Autorizační scope zahrnuje běžné nutné provozní kroky pro odsouhlasený cíl a omezený vznik označených syntetických testovacích cases, ne mazání, změny externího DB schématu nebo zásahy do cizích služeb. Oddělený mock cloud deploy není podmínka DB nasazení.

**Rozhodnutí před deployem: cílové prostředky.** Read-only AWS inspekce identifikovala existující `wonderfulkb-case-client` s runtime `nodejs22.x`, API `bgm7k1ggqi` a sdílenou execution role `wonderfulkb-lambda-role`. Náš artefakt má runtime Python3.13 a SAM vlastní API/roli; stejné business jméno neprokazuje vlastnictví ani povolení k přepsání. Před deploymentem vybrat buď nový izolovaný testovací SAM stack/API nad existujícími tabulkami (bez přepnutí starého endpointu), nebo výslovně autorizované převzetí existující služby po inspekci integrací a uchování rollback artefaktu/konfigurace. Nevytvářet paralelní stack bez rozhodnutí o cíli, nepřepisovat existující Node.js Lambdu a nepřepojovat její gateway jen podle jména.

Host naváže po úspěšné kódové přejímce a registrovaných testech: ověří cílový účet/region/stack a nasazované bajty, připraví rollback k předchozí známé verzi či bezpečnou izolaci nového stacku, zkontroluje change set a least-privilege rozsah, nasadí, ověří skutečný backend/role/tabulky a spustí čtecí i autorizované zápisové scénáře integračního runneru. Klíče získává pouze do bezpečného runtime prostředí a neukládá je do repozitáře ani reportu. Změny prostředků mimo dohodnutý scope nebo destruktivní replacement znamenají zastavení před provedením.

**Definice hotového výsledku:** úspěšné lokální/nezávislé kódové brány + důkaz konkrétního nasazeného artefaktu, URL/backendu a úspěšný plný HTTP integrační report. Kódový terminal status sám neznamená dokončené nasazení. Chybějící testovací data se reportují jako konkrétní blocker (`NOT_READY`), nezakládají oprávnění k seedu externích clients a nedovolují přejmenovat čtecí subset na plnou přejímku. V případě skutečné kódové chyby z live testu zachovat report a zadat cílenou opravu kanonickému coding ownerovi; host ji neopravuje ručně.

## Nejmenší technické řešení <!-- section:decisions type:context -->

- Python 3.13, standardní knihovna, jedna Lambda, jeden handler, malá Case/Client repository hranice a mock adaptér nad zabalenými JSON fixtures. Žádný web framework, ORM, boto3 nebo databázové prostředky v první části.
- Použít existující čtyři HTTP operace. API Gateway **REST API**, stage `v1`, `x-api-key`, jeden klíč a jednoduchý usage plan zachovávají stávající OpenAPI. Nezaměňovat za HTTP API nebo veřejný Function URL bez klíče jen kvůli kratšímu deployi.
- Jedna malá SAM šablona pro Lambdu/API/klíč/usage plan/logy. **SAM není podmínka AWS Lambdy**, ale je tu nejjednodušší opakovatelný zápis těchto prostředků. Ruční ZIP+CLI by byl možný, znamenal by však zvlášť nastavovat gateway, oprávnění a klíč. CDK ani další infrastrukturní vrstvu nepřidávat.
- Bez externích Python závislostí lze zdroj v `CodeUri` zabalit při `sam deploy`; container build není povinný. Lokální brána: standardní `unittest`, `compileall`, validace šablony. `sam build`, pokud bude užitečný, nativně; **nevyžadovat Docker, `--use-container`, `sam local start-api`, DynamoDB Local ani LocalStack**.
- Requesty se ověřují přímo jako uložené API Gateway REST proxy eventy. Skutečná gateway/API key se ověří až nasazeným smoke. Žádný druhý lokální HTTP server.
- Mock režim musí být explicitní: `DATA_BACKEND=mock`, `ALLOW_EPHEMERAL_MOCK=true`. Chybějící/neznámý režim selže jasně. Žádný tichý přechod ze skutečné DB na mock. V odpovědích `X-Data-Backend: mock` a v README výrazně označené demo bez persistence.

### Co mock znamená

Mock umí číst několik syntetických klientů a cases a simuluje zakládání do paměti **jednoho Lambda execution environmentu**. V rámci jedné instance drží stejné business chování a idempotenci jako zamýšlená služba. Při cold startu se obnoví fixtures; různé instance mohou mít různý stav. Není to sdílené ani trvalé úložiště a nelze slíbit, že vytvořený case půjde přečíst dalším HTTP požadavkem. Ani omezení concurrency tuto záruku nezajistí.

Tato dočasná odchylka od trvalého API kontraktu musí být výslovně přiznaná, ne označená za plnou DB integraci. Read smoke používá **předem zabalený case**, nikoli výsledek předchozího POST. POST ověřuje tvar/201, ne cloudovou end-to-end persistenci. Pokud demo vyžaduje spolehlivý create→read napříč požadavky, druhá fáze nebo jiné skutečné úložiště je nutné; v první fázi nic takového nepřidáváme.

## Část 1: Lambda s mock daty, lokální test a připravený deploy <!-- section:lambda-mock -->

**Jeden implementační výsledek:** nasaditelná komponenta `be-case-client/`, bez databázového připojení. Konkrétní repo-local brief je v `plans/tasks/2026-10-19_case-client-lambda-mock.md`.

- Implementovat `GET /clients`, `POST /cases`, `GET /cases/{case_id}`, `GET /clients/{client_id}/cases` podle stávajících datových tvarů, filtrů, stránkování a business pravidel. Změny persistence mocku jsou dokumentované výše, nikoli skryté.
- Syntetické fixtures: aktivní/neaktivní/blokovaný klient, diakritika a právní forma v názvu, známé case ID a klient bez cases. Při načtení pracovat s kopií, ne s měněným globálním souborem.
- Lokálně testovat všechny routy a chyby včetně 201/200/409 idempotence uvnitř jedné repository instance, obnovení fixtures v nové instanci a neexistující klient/case. Žádné AWS credentials ani síť. Testy ukládat v komponentě, neměnit backoffice.
- SAM šablona vystaví stejné routy, JSON 403/429, API key ochranu; žádná DynamoDB/S3/RDS oprávnění, cloudové databáze, VPC, CI/CD nebo provisioned concurrency. CloudWatch logy s krátkou retention, bez logování API klíče/obsahu klientů.
- README: offline příkazy, nasazení testovacího stacku `wonderfulkb-case-client-mock` v `eu-central-1` přes `ai-hackathon`, bezpečné získání klíče mimo repozitář, smoke a odstranění pouze mock stacku. Výstupy nesmí zveřejnit API key, jen URL a potřebné nesekretní identifikátory.

**Přejímka kódu:** offline testy, syntaktická kontrola a `sam validate --lint` projdou; současné frontend testy/build zůstanou zelené. Stejný handler i mock adaptér jsou otestované dohromady. Staticky ověřit, že stack neobsahuje databázové prostředky/oprávnění. README zřetelně uvádí nemožnost garantovat trvalou či meziinstanční idempotenci.

**Provozní návaznost hosta:** po přijetí kódu samostatně provést autorizovaný deploy a smoke: GET syntetických klientů, GET zabaleného case, seznam cases, POST/201, chyba 404/409 na fixtures, bez klíče/špatný klíč 403. Nikdy netvrdit, že POST→následný GET dokazuje persistenci. Žádné DB operace. Ověřit URL a skutečné nasazené artefakty; lokální test není důkaz cloudového běhu.

## Předané připojení a ověřený DB kontrakt <!-- section:db-connection type:context -->

Zdroj: sdílená quick-connect poznámka dodaná Michalem 19. 10. 2026. Její API klíč není součástí proposalu ani task briefu; nekopírovat jej do repozitáře, fixture, příkazové historie nebo logů. Privátní `dynamo.md`/`aws.md` nejsou dostupné implementační vstupy. Jejich obsah nenahrazujeme domněnkami.

**Ověření připojení:** host provedl pouze `sts get-caller-identity` a `dynamodb describe-table` obou tabulek. Níže je ověřená struktura prostředků; ne důkaz funkčního adaptéru, API, seed dat nebo práv k zápisu. Bez čtení položek, HTTP volání, zápisů či deploye. Tabulky jsou externě vlastněné, ne prostředky našeho SAM stacku.

- Region `eu-central-1`, AWS účet `609394381050`; obě tabulky mají on-demand billing.
- Clients: `wonderfulkb-uw-clients`, ARN `arn:aws:dynamodb:eu-central-1:609394381050:table/wonderfulkb-uw-clients`; partition key `client_id` (String), bez sort key. GSI `ico-index`: partition key `ico` (String), projekce `ALL`.
- Cases: `wonderfulkb-uw-cases`, ARN `arn:aws:dynamodb:eu-central-1:609394381050:table/wonderfulkb-uw-cases`; partition key `case_id` (String), bez sort key. GSI **`client-created-index`**: partition key `client_id` (String), sort key `created_at` (String), projekce `ALL`.
- Index `client-created-index` nahrazuje nepotvrzené starší jméno `client-created-at-index` ze zdrojového plánu; nezakládat další index jen kvůli starému návrhu. Timestampy musí mít jednotnou UTC reprezentaci pro správné lexikografické řazení.
- Lokálně existuje AWS profil **`ai-hackathon`**; v předané poznámce je profil `hackathon`. To je lokální alias, nikoli součást DB protokolu. Nepřejmenovávat profil ani nepřidávat credentials do aplikace. Pro Lambdu použít execution role a standardní SDK credential chain, nikdy uživatelský SSO profil.
- DynamoDB nemá DB heslo ani samostatný DB port. SDK používá HTTPS a IAM/SigV4, standardní regionální endpoint; poznámka nevyžaduje IP allowlist. Nepřidávat VPC, security groups nebo proxy pouze kvůli připojení.

**Externí HTTP API — předaný údaj, ne náš deploy:** `https://bgm7k1ggqi.execute-api.eu-central-1.amazonaws.com/v1`, autentizace `x-api-key`. Poznámka uvádí stejné čtyři routy jako OpenAPI a limity 10 req/s, burst 20; 403 bez správného klíče, 404 neznámé entity, 409 business konflikt, 429 throttling. Uvádí jednoho syntetického klienta a jeden case, nikoli dokončený seed. Tato tvrzení nebyla HTTP smoke testem ověřena. Lambda se připojuje **přímo do DynamoDB**, ne přes toto API a nepotřebuje jeho API klíč. Existující API/stack/role nesmí být nasazením naší komponenty nechtěně nahrazeny; případné převzetí jeho vlastnictví vyžaduje samostatné provozní rozhodnutí.

Schema klíčů a projekce indexů jsou ověřené. Zbývá potvrdit datové tvary položek vůči OpenAPI, zejména reprezentaci `created_at`, metadata/čísel a případné pomocné atributy normalizovaného názvu. Samotné `DescribeTable` nepotvrzuje tyto atributy ani oprávnění k business operacím.

## Část 2: Připojení skutečné externí databáze <!-- section:external-db -->

**Výsledek:** stejný handler a čtyři HTTP operace používají jediný nový DynamoDB repository adaptér. Mock zůstává pouze explicitním demo/test režimem. Žádná druhá služba nebo HTTP proxy. Implementační brief: `plans/tasks/2026-10-19_case-client-dynamodb-adapter.md`. Jeden výsledek zahrnuje adaptér i samostatně spustitelný HTTP integrační runner podle návrhu níže; samotný cloudový deploy a spuštění live testů vlastní host.

### Rozsah adaptéru

- `DATA_BACKEND=dynamodb` vybere nový adaptér; `DATA_BACKEND=mock` zachová původní explicitní opt-in. Žádný fallback do mocku při chybě credentials, konfigurace nebo DB. Hlavička skutečného režimu `X-Data-Backend: dynamodb`.
- Konfigurace přes `CLIENTS_TABLE_NAME`, `CASES_TABLE_NAME`, `CLIENTS_ICO_INDEX_NAME=ico-index`, `CASES_CLIENT_CREATED_INDEX_NAME=client-created-index` a standardní AWS region. Přidat minimum SDK závislostí a reprodukovatelné SAM balení; bez ORM, Dockeru nebo lokální DB jako povinné součásti testů.
- `GetItem` pro primární klíče; `Query` na `ico-index` pro přesné IČO; `Query` na `client-created-index` s `ScanIndexForward=false` pro seznam cases od nejnovějšího. GSI má eventual consistency, neslibovat okamžitý výskyt nového case v indexovém seznamu. Přímý get-case a řešení idempotence používají silně konzistentní čtení tabulky.
- Bez IČO je vyhledávání klientů pro malý syntetický hackathon dataset stránkovaný `Scan`. Normalizaci názvu sdílet s mockem; nespoléhat na neověřený atribut `name_normalized`. AND filtry, limit i pokračovací token zachovávají veřejný kontrakt. DynamoDB `Limit` omezuje vyhodnocené položky, ne počet výsledků po filtrování; prázdná interní stránka neznamená konec. Token validovat a vázat na backend/dotaz, bez duplicit, ztrát a neomezeného scan loopu. Výslovně nejde o škálovatelné fulltextové řešení.
- Case vytvářet atomicky bez přepsání existujícího `case_id`. Trvalá idempotence: stejné ID+klient → původní case/200 i po změně klientova statusu; jiné vlastnictví →409. Nový case vyžaduje existujícího aktivního klienta; pokud se jeho stav změní souběžně se zápisem, transakční kontrola zabrání založení. Použít `TransactWriteItems` s kontrolou klienta a podmíněným vložením case nebo prokazatelně ekvivalentní atomickou operaci. Konflikt závodu rozhodnout konzistentním opětovným čtením; neodhadovat výsledek z každé SDK výjimky.
- Chyby DB/permissions/timeout/throttling nerozlišovat jako prázdný úspěch nebo falešnou 404/409. Bezpečná 5xx odpověď `{"error":"..."}`, sanitizované logy. Metadata zachovají podporované JSON číselné typy i v boto3/Decimal; limit z první části zůstává dokumentovaný a SDK item-size chyby nesmějí poškodit již uložený case.
- SAM pouze odkáže na externí tabulky/indexy a přidá least-privilege role policy pro nezbytné čtení, vložení a transakční kontrolu. Read-only oprávnění z quick-connect nestačí pro `POST /cases`. Žádné vytváření/úpravy/mazání tabulek a indexů, seed, DeleteItem/UpdateItem či široké `dynamodb:*`.

### Ověření a provozní hranice

**Přejímka kódu:** zachované behavior testy mocku, handler přepnutý na skutečný adaptér se stubovaným SDK (např. botocore Stubber), přesné požadavky na tabulky/indexy, validace tokenů a pokračování po prázdných filtrovaných stránkách, serializace, konflikty transakcí a trvalá idempotence při nových instancích adaptéru, chybové scénáře. Offline bez AWS účtu, credentials a sítě. Zachovat frontend bránu, validovat SAM i least-privilege rozdíl pro mock/DB režim. Lokální stuby neprokazují skutečný cloudový souběh nebo persistenci.

**Host v rámci autorizovaného end-to-end cíle po rozhodnutí o cílovém nasazení:** ověřit skutečná data/oprávnění a vlastnictví cílového nasazení, pak deploy a omezený smoke se syntetickými identifikátory: create→strong read, opakování→200 bez přepsání metadat, konflikt a souběh, GSI výpis s omezeným čekáním na propagaci. Bez automatického mazání dat. Runtime připojení, nasazení a end-to-end persistence jsou samostatná tvrzení s vlastními důkazy. Pouhá úprava dokumentace neautorizuje libovolné cloudové efekty. Nové prostředky/klíč pouze jako součást odsouhlaseného cílového stacku; označené syntetické case zápisy pouze podle testovacího scope výše, žádný seed klientů.

## Integrační test po nasazení — návrh v rámci DB adaptéru <!-- section:deployed-integration type:context -->

Tento návrh je součástí implementačního výsledku `external-db`, nikoli třetí implementační task. Dodat explicitně spouštěný Python HTTP runner `be-case-client/tests/integration/case_client_api_integration.py` a offline testy jeho chování; běžný unit/test gate nesmí provádět síťové nebo AWS operace. Testuje skutečné API Gateway → Lambda → DynamoDB, ne přímé volání handleru či mock repository. Stačí standardní HTTP knihovna, bez nového serveru nebo frameworku.

### Vstupy a bezpečné spuštění

- Host předá `CASE_CLIENT_BASE_URL` (HTTPS, očekávaný host a stage ověřený proti cílovému deploymentu), `CASE_CLIENT_API_KEY` jen přes prostředí a nesekretný syntetický fixture manifest. Žádný vestavěný endpoint ani API klíč; zakázat přesměrování s credential hlavičkou. Bez klíče/URL/manifestu jasná chyba před sítí, ne úspěch nebo automatický výběr cizí služby.
- Manifest: známý aktivní klient (ID, IČO, očekávaný název), předem uložený case; pro plný scénář druhý aktivní klient, inactive/blocked klienti a dost dat pro dvě stránky. Manifest je syntetický, bez credentialů. Nezaložit si tyto klienty přímo do DB: API je read-only pro clients, fixture data spravuje DB tým.
- Výchozí režim `read-only`, očekávaný backend explicitně `dynamodb` nebo `mock`. Zápisový režim pouze s `--allow-writes`, `--expected-backend dynamodb` a unikátním `run_id`. POST se spustí až po úspěšném ověření cíle, klíče a markeru DB režimu. Mock smoke nikdy neoznačit jako důkaz DB persistence.
- Pevné limity requestů, timeoutů a celkového času; konzervativně pod předaným 10 req/s/burst20, žádný zátěžový test. Přesné limity/limity stránek budou v README. Bounded retry jen pro bezpečné čtení a očekávanou GSI propagaci; POST timeouts/5xx zapsat jako nejednoznačný výsledek, ne slepě přehrávat. Neprovádět 429 test zahlcením shared API; doložit ho offline/šablonou, live jen ve zvlášť autorizovaném izolovaném testu.

### Scénáře přes skutečné HTTP rozhraní

1. **Preflight/read-only:** bez API key a s neplatným klíčem403 bez následování redirectu; s klíčem očekávaná JSON odpověď a marker backendu. GET clients přes IČO a kombinaci name/status, ověření známé syntetické identity/normalizace. GET předem známého case a GET cases klienta — tím jsou čtecí routy ověřené bez zápisů. Neznámý case/klient404, neplatný filtr/limit/token400. Ověřit veřejné response typy, žádné interní DB atributy a JSON error tvar.
2. **Stránkování a řazení:** limit1 a následování next_token, bez cyklů/duplicit, zachování filtrů, cases newest-first. Ověřit alespoň dvě stránky nad stabilními fixtures a odmítnutí tokenu s jiným dotazem; jeden klient/case nemůže tento scénář prokázat. Test nemá předepsaný total-order tie-break nad shodnými created_at, pokud jej kontrakt negarantuje.
3. **DB zápisový průchod:** nový case ID `it-<run_id>-persist`, malé syntetické metadata →201; ověřit vrácené ID/client/status/created_at. Následný GET z nového HTTP spojení →tentýž obsah. Opakovaný POST se stejným ID+klientem a jinými metadata →200 a původní metadata/čas. Stejné ID s jiným známým klientem →409, původní case nezměněn. Neexistující klient404, inactive/blocked409 a po odmítnutém založení GET nového ID404.
4. **Indexová propagace:** hledat právě vytvořený case v seznamu klienta v omezeném počtu stránek/pokusů s celkovým deadline. GSI může být dočasně prázdný; po deadline test selže s přesným scénářem, neskrývat výsledek. POST/GET tabulky se neposouvá na eventual consistency jen proto, že index má zpoždění.
5. **Malý souběh, jen write režim:** dvě současná volání na druhé unikátní case ID se stejným klientem →jeden201 a jeden200, stejné uložené hodnoty. Další ID a dva různí aktivní klienti →jeden201 a jeden409, GET odpovídá vítězi. Maximálně dva souběžné requesty a omezený celkový počet. Žádné přepínání statusu klienta v živé DB; tento závod zůstává součástí offline SDK testů.

### Výsledek a interpretace

- Strojově čitelný JSON report a stručný console summary: run_id, čas, nesekretný cílový host/stage, očekávaný/pozorovaný backend, pokryté scénáře, HTTP statusy, časy, vytvořená syntetická case ID a chyby. Žádné request headers, API klíče, celé klientské objekty/metadata nebo raw response dumpy. Výstupy host ukládá mimo verzované soubory.
- Exit0 znamená všechny povinné scénáře zvoleného profilu prošly; HTTP/assertion chyba i chybějící povinné fixtures mají nonzero. Chybějící druhý klient nebo více stránkovatelných dat se evidují jako `NOT_READY`, ne PASS. Čtecí subset musí být označen `read-only`, nikdy jako plná DB přejímka. Aktuálně předaný jeden klient/case nedostačuje k plnému scénáři.
- API nemá DELETE: test ponechá několik jasně označených syntetických cases; před spuštěním odsouhlasit jejich vznik a případný úklid DB vlastníkem. Runner nesmí přidat DELETE endpoint, práva k mazání, přímé DB čtení nebo seed.
- Úspěšný DB-marker + HTTP zápis/čtení prokazuje end-to-end chování nasazené konfigurace spolu s ověřenou rolí/tabulkami a artefaktem. Nové HTTP spojení samo nevynutí novou Lambda instanci, takže nejde o důkaz více execution environments. Neprovádět cold-start forcing, restart, concurrency změny nebo paralelní invokační nástroje kvůli tomuto tvrzení.
- Deploy a spuštění live testů jsou oddělené host operace uvnitř společného end-to-end zadání; po vyřešení cílového prostředku a skutečných bezpečnostních blockerů nevyžadují nové obecné zadání. Coding task dodá runner a ověří ho offline se simulovaným HTTP transportem, včetně no-secret reportu, write opt-in, neznámého výsledku POST, chybějících fixtures, bounded retry a GSI timeoutu. Tento návrh sám žádné live provolání nespouští.
