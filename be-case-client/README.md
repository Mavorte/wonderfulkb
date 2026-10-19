# wonderfulkb Case & Client

Jedna Python Lambda, pět operací a OpenAPI 1.5.0. Repository
hranice má dva explicitní režimy: ephemeral mock a externí DynamoDB adaptér.
Žádný fallback. Komponenta obsahuje deploy nástroj
`tools/case_client_test_deploy.py` a HTTP runner
`tests/integration/case_client_api_integration.py` (výchozí režim read-only).
**Live integrace není dokončena; stav je BLOCKED.** Lokální testy ani hlavička
`X-Data-Backend` nenahrazují důkaz celé HTTP/DB matice.

## Stav integračního pokusu

Historický ledger pro `task-beca6825-147b-43d9-9fb6-694368e70948` zaznamenává
Python deploy na původní Lambda/API a úspěšné read-only scénáře. První POST
vrátil 500; chybí `dynamodb:ConditionCheckItem` na clients tabulce a SCP brání
úplnému zjištění uživatelů sdílené role. IAM se neměnilo. Po rollbacku ledger
dokládá původní `nodejs22.x` / `handler.handler` a recovery smoke 403/403/200.
To je historická evidence, nikoli nový cloudový readback této session.

- Cíl: profil `ai-hackathon`, účet `609394381050`, region `eu-central-1`,
  Lambda `wonderfulkb-case-client`, API `bgm7k1ggqi`, stage `v1`.
- Vyčerpáno **5/5 deploy pokusů**; zůstaly čtyři syntetičtí klienti a jeden
  neověřený POST, žádné potvrzené case ID. Ledger se nesmí vynulovat.
- Další live běh nebo mutace v tomto tasku nejsou povoleny. Nový pokus vyžaduje
  výslovné zadání s novým rozpočtem a vyřešeným přístupem.
- Offline review stále nachází vady deadline/recovery a evidence při resume.
  Nová regrese deadline po limiteru selhává. Povinný proof helper odmítá nový
  RED nad již dokončeným kanonickým proof; původní důkaz se nepřepisuje.

Sanitizovaná evidence a aktuální review:
[`manifest.json`](../plans/checkpoints/case-client-live-integration/task-beca6825-147b-43d9-9fb6-694368e70948/manifest.json),
[`review-current.md`](../plans/checkpoints/case-client-live-integration/task-beca6825-147b-43d9-9fb6-694368e70948/review-current.md).
Původní `review.md` zůstává historickým review staršího snapshotu.

## Instalace a lokální ověření

Lokální Python 3.9+, cílový Lambda runtime Python 3.13. Runtime SDK, JSON knihovna
i transitivní závislosti jsou připnuté v `src/requirements.txt`. Dev manifest
odkazuje na stejný lock; unittest je standardní knihovna, Stubber dodává botocore.

```sh
PY=/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python
"$PY" -c 'import sys, boto3, botocore, simplejson; assert sys.version_info[:2] == (3, 13)'
PYTHONPATH=be-case-client/src "$PY" -m unittest discover -s be-case-client/tests -p 'test_*.py' -v
"$PY" -m compileall -q be-case-client/src be-case-client/tests be-case-client/tools
npm --prefix apps/backoffice test
npm --prefix apps/backoffice run build
```

Testy DB používají explicitní falešné credentials, `/dev/null` místo AWS configu
a credentials souboru, vypnuté metadata discovery a zákaz socket/DNS. Nepotřebují
profil, SSO, Docker, DynamoDB Local, LocalStack, server ani API klíč. Stubber
ověřuje přesné SDK požadavky i simulované transakční interleavingy, ne skutečný
cloudový souběh. Mock factory neprovádí SDK inicializaci ani credential discovery.

## Konfigurace

| Proměnná | Hodnota / pravidlo |
|---|---|
| `DATA_BACKEND` | Povinné `mock` nebo `dynamodb` |
| `ALLOW_EPHEMERAL_MOCK` | Pouze pro mock povinné přesně `true` |
| `CLIENTS_TABLE_NAME` | DB povinné, host kontrakt `wonderfulkb-uw-clients` |
| `CASES_TABLE_NAME` | DB povinné, host kontrakt `wonderfulkb-uw-cases`, odlišná tabulka |
| `CLIENTS_ICO_INDEX_NAME` | DB povinné, host kontrakt `ico-index` |
| `CASES_CLIENT_CREATED_INDEX_NAME` | DB povinné, host kontrakt **`client-created-index`** |
| `AWS_REGION` / `AWS_DEFAULT_REGION` | DB povinný region, první má přednost; host `eu-central-1` |

Názvy tabulek/indexů jsou 3–255 ASCII písmen/číslic/`_.-`; prázdná či neplatná
konfigurace selže i při injekci repository. Neznámý backend a selhání SDK nikdy
neaktivují mock. Warm handler se při změně konfigurace znovu vytvoří. Aktivovaný
handler vrací `X-Data-Backend: mock` nebo `dynamodb` také u chyb. Chyba konfigurace
či inicializace vrací sanitizovanou 500 bez falešného backend markeru.

Lambda používá **execution role**, nikoli profil, API klíč nebo DB heslo. Hostův
lokální SSO alias `ai-hackathon` používají pouze komponentové live nástroje.
API key kontroluje API Gateway, ne Python handler; není DB credential.

## Chování

- Každý POST `/cases` generuje nové UUIDv4 na serveru, ignoruje jakékoli
  dodané `case_id` a při úspěchu vrací 201. Aktivní klient → `status=open`, UTC čas;
  neexistující klient →404, inactive/blocked →409.
- GET `/cases` vrací veřejné case napříč všemi klienty stránkovaným Scanem tabulky
  cases. Neověřuje ani nečte klienty; globální pořadí není garantováno. Cursor je
  route/query/limit/backend vázaný. Klientské listování zůstává newest-first GSI Query.
- DB nejprve konzistentně ověří klienta. Zápis je `TransactWriteItems`:
  existence a active status klienta + `attribute_not_exists(case_id)` při Put.
  Condition konflikt se klasifikuje podle přesné pozice cancellation reasonů.
  Kolize case klíče se ověří strong readem a zahodí; generátor zkusí nejvýše
  tři UUID. Occupant se nikdy nevrací ani nepřepisuje. Nevyřešené/ambiguous
  cancellation, exhaustion, permission, throttling a timeout jsou sanitizované 5xx.
- Přímý detail a kontroly klienta jsou `GetItem` s `ConsistentRead=true`.
  Seznam cases nejprve ověří klienta, pak Query `client-created-index`,
  `ScanIndexForward=false`, bez nepodporovaného strong read GSI. GSI je
  **eventually consistent**: okamžitý seznam po POST není garantovaný. Stejné
  timestampy nemají veřejný tie-break slib. Klient bez cases má prázdný seznam.
- Klienti: přesné IČO přes Query `ico-index`, jinak Scan pro malý syntetický
  dataset. AND filtry status/název se vyhodnocují v adaptéru. Normalizace názvu
  je společná s mockem (casefold, diakritika, celé právní formy). Žádný požadavek
  na `name_normalized` nebo nový index. Scan nemá globální třídění; není fulltext
  pro velká data a spotřebovává read kapacitu i za nezobrazené položky.
- Veřejný limit 1–100, default 50. SDK PageSize `min(limit,25)` omezuje vyhodnocené
  položky, ne počet shod; adapter pokračuje i přes prázdné filtrované stránky
  a 1MB hranice. Nejvýše 8 SDK stránek (200 vyhodnocených položek), časový budget
  7 s, rezerva 3 s před dalším voláním, případně kratší zbývající Lambda čas.
  SDK connect/read timeout 1/2 s, total attempts 1. Nedostatek času před první
  stránkou je 5xx; po čtení může přijít neplná/prázdná stránka s pokračováním.
- Token je max 4096 znaků, kanonický verzovaný base64url JSON s přesným schématem
  a stringovými AttributeValue klíči. Je svázaný s backendem, regionem, oběma
  tabulkami/indexy, operací, klientem, normalizovanými filtry a limitem. Cizí či
  neplatný token →400 před SDK. Při naplnění limitu uprostřed SDK stránky obsahuje
  klíč poslední vydané položky, ne LEK konce stránky; jinak obsahuje LEK. Funguje
  napříč instancemi, bez uchovávání objektů v tokenu. Token není autentizace ani
  šifrování a při souběžných změnách **není snapshotová konzistence**.
- Metadata musí být objekt do **16384 bajtů kompaktního UTF-8 JSON**. Null,
  boolean, integer, desetinná čísla i vnořené seznamy/mapy se zachovají.
  JSON requesty/odpovědi používají simplejson/Decimal bezeztrátově, SDK
  TypeSerializer/TypeDeserializer. Přímé Python float vstupy se převádějí přes
  jejich JSON zápis na Decimal. NaN/Infinity, DynamoDB-nekompatibilní čísla/typy
  a příliš hluboké objekty se odmítnou před
  zápisem. Interní atributy se nevracejí; nekompatibilní uložená data →500 bez
  vymyšlených hodnot. Metadata mohou v uloženém case chybět.
- Chyby mají `{"error":"..."}`. Provozní chyby ani neexistující tabulka nejsou
  business 404 nebo prázdný úspěch. Aplikace neloguje payloady či SDK detaily;
  nezapínat SDK wire/debug logy. Neplatné path ID →400, neznámá route →404,
  nesprávná metoda →405. Veřejné serializátory mají allowlist.

### Ephemeral mock

Mock má zabalené syntetické fixtures a vlastní lock/deep copies. Stav nových
cases žije jen v jedné repository/execution environmentu, cold start
obnoví fixtures. Žádná globální persistence ani POST → další HTTP GET záruka.
Klienty třídí podle client_id, cases nejnovější první s case_id tie-breakem.
Kurzory nad neměnnými fixtures jsou meziinstanční; nová ephemeral data mohou po
resetu chybět. Oddělovat mock, offline test a případné budoucí live prostředky.

## SAM šablona a komponentové balení

Šablona `template.yaml` je JSON (YAML podmnožina), stále sedm prostředků, jedna
Python 3.13 Lambda/256MB/10s, čtyři API-key chráněné REST routy, stage v1,
key/usage plan a scoped log group s retencí 7 dní. Gateway 403/429 zůstávají
oddělené od aplikačních chyb. Outputs mají ID klíče, nikdy jeho hodnotu.

Parametry: `DataBackend` (default `mock`), `ClientsTableName`, `CasesTableName`,
`ClientsIcoIndexName`, `CasesClientCreatedIndexName` (defaults dle tabulky env),
`ExternalTablesAccountId` (default `609394381050`). Region vezme Lambda z AWS;
rezervovaný env `AWS_REGION` se v šabloně nenastavuje. Žádné DB resources,
seed, migrace, VPC nebo přebírání tabulek do stacku.

Mock role má jen scoped `logs:CreateLogStream`/`logs:PutLogEvents`. Pouze při
`DataBackend=dynamodb` podmíněná policy přidává následující přesná oprávnění
na prefixu `arn:${AWS::Partition}:dynamodb:${AWS::Region}:${ExternalTablesAccountId}:table/`:

| Resource suffix | Akce |
|---|---|
| `${ClientsTableName}` | `GetItem`, `Scan`, `ConditionCheckItem` |
| `${ClientsTableName}/index/${ClientsIcoIndexName}` | `Query` |
| `${CasesTableName}` | `GetItem`, `PutItem` |
| `${CasesTableName}/index/${CasesClientCreatedIndexName}` | `Query` |

Akce mají prefix `dynamodb:`. TransactWriteItems autorizuje jednotlivé akce;
nepřidává se transakční wildcard. Read-only host oprávnění nestačí na POST.
Žádný DeleteItem/UpdateItem ani jiné tabulky. Případný cross-account přístup
potřebuje i odpovídající externí resource policy, kterou vlastní host.

Offline lint z kořene (tuto šablonu pro existující testovací cíl nenasazovat):

```sh
AWS_REGION=eu-central-1 AWS_DEFAULT_REGION=eu-central-1 AWS_EC2_METADATA_DISABLED=true AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_ACCESS_KEY_ID=offline AWS_SECRET_ACCESS_KEY=offline SAM_CLI_TELEMETRY=0 /Users/michal/.local/bin/sam validate --lint --template-file be-case-client/template.yaml
```

Komponentový deploy nástroj balí současné `src/*.py` a připnuté dependencies
pro Linux x86_64 / CPython 3.13, ověřuje simplejson ELF a upload limit.
Používá existující pip nebo uv; macOS venv není deploy artefakt. ZIP se nahrává
přímo do existující Lambdy s RevisionId a waitery, bez S3/CloudFormation.

**Před jakýmkoli budoucím nasazením** host samostatně ověří vlastnictví cílového
API/role a write práva. Původní čtyři AWS_PROXY metody, klíče a throttles se
zachovávají. Profil `ai-hackathon` je jen lokální host SSO, nikdy env aplikace.
Explicitní write opt-in a run ID nejsou povolením resetovat vyčerpaný rozpočet.

Preflight kontroluje klíče/indexy a ALL projekce. Při práci s daty je dále nutné
ověřit nekličové atributy proti OpenAPI, zejména:

1. `created_at`: jednotný UTC string, přesnost a lexikografická kompatibilita
   s novými `YYYY-MM-DDTHH:MM:SS.ffffffZ`; různé formáty mohou změnit GSI pořadí.
2. Metadata jako DynamoDB map odpovídající JSON objektu/číslům, bez binárních/set
   hodnot; optional nepřítomnost je podporovaná, null místo objektu nikoli.
3. Client `status` přesně active/inactive/blocked a další veřejné typy/enumy;
   nespoléhat na pomocné atributy, nedoplňovat chybějící business hodnoty.

Úplná persistence a souběžná HTTP matice zůstávají neprokázané. Statické IAM/SAM
testy ani Stubber tyto důkazy nenahrazují; stav zůstává BLOCKED.
