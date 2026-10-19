# wonderfulkb Case & Client

Jedna Python Lambda, čtyři operace a nezměněné OpenAPI 1.3.0-final. Repository
hranice má dva explicitní režimy: ephemeral mock a externí DynamoDB adaptér.
Žádný fallback. Tato implementace je ověřovaná pouze lokálně pomocí SDK Stubberu
a skutečného handleru; cloudové připojení, gateway, persistence a souběh v AWS
nejsou lokálními testy prokázané. HTTP integrační runner je odložený návrh
v proposalu, nikoli součást této komponenty.

## Instalace a lokální ověření

Lokální Python 3.9+, cílový Lambda runtime Python 3.13. Runtime SDK, JSON knihovna
i transitivní závislosti jsou připnuté v `src/requirements.txt`. Dev manifest
odkazuje na stejný lock; unittest je standardní knihovna, Stubber dodává botocore.

```sh
python3 -m venv .venv-case-client
. .venv-case-client/bin/activate
python3 -m pip install -r be-case-client/requirements-dev.txt
PYTHONPATH=be-case-client/src python3 -m unittest discover -s be-case-client/tests -p 'test_*.py' -v
python3 -m compileall -q be-case-client/src be-case-client/tests
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
lokální SSO alias `ai-hackathon` patří výhradně do budoucího host runbooku.
API key kontroluje API Gateway, ne Python handler; není DB credential.

## Chování

- Společná pravidla: stejné case ID + klient →200 s původním časem/metadata,
  jiný vlastník →409. Existující case má přednost i před nyní inactive/blocked
  nebo odstraněným klientem. Nový case pro neexistujícího klienta →404,
  inactive/blocked →409; aktivní →201, `status=open`, UTC čas.
- DB nejprve konzistentně čte case. Nový zápis je jediný `TransactWriteItems`:
  existence a active status klienta + `attribute_not_exists(case_id)` při Put.
  Condition konflikt vyvolá jeden konzistentní read-back průchod: vítěz stejného
  klienta →200, jiný →409; změněný/smazaný klient →409/404. Nevyřešený závod →500.
  Smíšené/chybějící cancellation reasons, transaction conflict, oprávnění,
  throttling a timeout jsou 5xx, nikoli automaticky 409. Žádné opakované zápisy
  v recovery. Při timeoutu není znám výsledek; další explicitní stejný POST
  může idempotentně přečíst skutečný výsledek.
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

Mock má zabalené syntetické fixtures a vlastní lock/deep copies. Stav/idempotence
nových cases žije jen v jedné repository/execution environmentu, cold start
obnoví fixtures. Žádná globální persistence ani POST → další HTTP GET záruka.
Klienty třídí podle client_id, cases nejnovější první s case_id tie-breakem.
Kurzory nad neměnnými fixtures jsou meziinstanční; nová ephemeral data mohou po
resetu chybět. Oddělovat mock, offline test a případné budoucí live prostředky.

## SAM artefakt a budoucí host runbook

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

Offline lint a nativní balení z kořene, pokud host má SAM/cfn-lint a Python 3.13:

```sh
AWS_REGION=eu-central-1 AWS_DEFAULT_REGION=eu-central-1 AWS_EC2_METADATA_DISABLED=true AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_ACCESS_KEY_ID=offline AWS_SECRET_ACCESS_KEY=offline SAM_CLI_TELEMETRY=0 sam validate --lint --template-file be-case-client/template.yaml
sam build --template-file be-case-client/template.yaml
```

Build je nativní, bez povinného Dockeru a bez `--use-container`. SDK a simplejson
se balí podle připnutého manifestu pro cílový runtime; nepoužívat samotné `src/`
bez dependencies. Budoucí host balení/deploy musí použít výstup
`.aws-sam/build/template.yaml`. Chybějící host runtime/SAM worker neinstaluje.

**Před jakýmkoli budoucím nasazením** host samostatně ověří vlastnictví cílového
API/stacku/role a write práva. Existující cizí API se neimportuje ani nepřebírá
automaticky. Profil `ai-hackathon` je jen lokální host SSO, nikdy env aplikace.
Nasazení není automatická návaznost tohoto tasku.

Host dosud ověřil pouze klíče/indexy a ALL projekce. Před použitím dat musí
potvrdit nekličové atributy proti OpenAPI, zejména:

1. `created_at`: jednotný UTC string, přesnost a lexikografická kompatibilita
   s novými `YYYY-MM-DDTHH:MM:SS.ffffffZ`; různé formáty mohou změnit GSI pořadí.
2. Metadata jako DynamoDB map odpovídající JSON objektu/číslům, bez binárních/set
   hodnot; optional nepřítomnost je podporovaná, null místo objektu nikoli.
3. Client `status` přesně active/inactive/blocked a další veřejné typy/enumy;
   nespoléhat na pomocné atributy, nedoplňovat chybějící business hodnoty.

Skutečné připojení, deploy, HTTP/gateway a persistence smoke zůstávají samostatnou
host fází s vlastními důkazy. Statické IAM/SAM testy ani Stubber tyto důkazy nenahrazují.
