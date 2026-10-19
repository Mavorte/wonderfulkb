# wonderfulkb Case & Client — EPHEMERAL MOCK

Jedna Python Lambda, syntetické zabalené fixtures a čtyři REST proxy operace podle
nezměněného `openapi-case-client.yaml` 1.3.0-final. **Není to produkční databáze.**
Žádné Python dependencies, AWS SDK, credentials lookup, síť ani zápis do `/tmp`.

## Chování a omezení dema

- Povinné přesné hodnoty `DATA_BACKEND=mock` a `ALLOW_EPHEMERAL_MOCK=true`.
  Factory odmítne jinou konfiguraci i při injekci repository. Veřejný vstup vrátí
  JSON 500 bez falešného markeru. Aktivovaný handler dává všem odpovědím včetně
  chyb `X-Data-Backend: mock` a `Content-Type: application/json`.
- Stav vytvořených cases žije pouze v jednom execution environmentu. Cold start
  obnoví fixtures, jiné instance mají nezávislá data. **Žádná trvalá, globální ani
  meziinstanční idempotence a žádná záruka HTTP POST → další GET.**
- `POST /cases` je prostý create: `case_id` generuje služba (UUID v4), v požadavku
  se neposílá a případné se ignoruje. Každé volání založí nový case (není
  idempotentní). Nový aktivní klient →201/open/UTC; neexistující →404,
  inactive/blocked →409. Create je atomický pod zámkem, nová repository má
  hlubokou kopii dat.
- `GET /clients`: AND filtry `ico`, `name`, `status`. Názvy ignorují velikost,
  diakritiku a celé právní formy s.r.o., a.s., v.o.s., k.s., společnost s ručením
  omezeným a akciová společnost (včetně mezer/teček). Řazení podle client_id.
- `GET /cases/{case_id}` a `GET /clients/{client_id}/cases`: nejprve existence
  klienta pro seznam; existující bez cases →prázdné pole. Nejnovější cases první,
  shodné časy podle case_id vzestupně; status pouze `open`.
- Limit 1–100, výchozí 50. Neprůhledný verzovaný kurzor je svázaný s endpointem,
  klientem, normalizovanými filtry, limitem a posledním ID; neplatný/cizí →400.
  Není autentizace, podpis ani šifrování a není to snapshot. Nad neměnnými fixtures
  funguje i mezi instancemi; nově vytvořená ephemeral data mohou po resetu chybět.
- Demo odchylky od zamýšlené DB verze: metadata objekt nejvýše **16384 bajtů**
  kompaktního UTF-8 JSON (`ensure_ascii=False`, bez NaN/Infinity); neplatné path ID
  detailu case →400 i když kontrakt tento status výslovně nevyjmenovává.
  Neznámá route →404, nepodporovaná metoda známé route →405. Chyby mají
  `{"error":"..."}`. Neočekávané/config chyby →500, nikoli úspěšný prázdný seznam.
  Neznámé vlastnosti request objektu nejsou zakázány; veřejná serializace má allowlist.

## Offline ověření z kořene repozitáře

Podporován lokální Python 3.9+ (ověřeno 3.9.6); cílový AWS runtime 3.13.
Unit testy nepotřebují SAM, Docker, server, přihlášení, síť nebo reálný API key.
Testy si konfiguraci i import path nastavují samy.

```sh
python3 -m unittest discover -s be-case-client/tests -p 'test_*.py' -v
python3 -m compileall -q be-case-client/src
npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build
```

Přímé volání skutečného handleru uloženým REST proxy eventem:

```sh
DATA_BACKEND=mock ALLOW_EPHEMERAL_MOCK=true python3 - be-case-client/events/list-clients.json <<'PY'
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path('be-case-client/src').resolve()))
from case_client_handler import lambda_handler
event = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
print(json.dumps(lambda_handler(event, None), ensure_ascii=False, indent=2))
PY
```

Argument lze nahradit `be-case-client/events/get-case.json`,
`be-case-client/events/list-client-cases.json` nebo
`be-case-client/events/create-case.json`. Každý nový proces obnoví fixtures.
Handler API key neověřuje: patří gateway. Statické testy SAM kontrolují strukturu,
neprokazují reálnou gateway ochranu. Factory `create_handler(repository)` přijímá
čtyřoperační `CaseClientRepository`; nový DB adaptér přijde až v další fázi.

## Host runbook: validace a deploy (v coding tasku se neprovádí)

Host potřebuje AWS SAM CLI (`sam`), AWS CLI, profil `ai-hackathon` a oprávnění
pro vytvoření těchto prostředků/IAM role. Šablona je JSON (platná YAML podmnožina).
Z kořene **nejprve skutečně validovat**:

```sh
sam validate --lint --template-file be-case-client/template.yaml
sam deploy --guided --profile ai-hackathon --region eu-central-1 --stack-name wonderfulkb-case-client-mock --template-file be-case-client/template.yaml --capabilities CAPABILITY_IAM
```

Použít přímé `CodeUri: src/` balení; `sam build` ani container build není nutný.
Guided deploy potvrdí vytvoření IAM role (`CAPABILITY_IAM`), API má key ochranu.
Neukládat odpovědi guided průvodce do repozitářového `samconfig.toml` (Save arguments:
N); případný deployment bucket spravuje SAM/host, služba nemá S3 oprávnění.
Jedna on-demand Lambda 256MB/10s, REST stage v1, klíč/usage plan,
log retention 7 dní; role pouze CreateLogStream/PutLogEvents vlastní skupiny.
Host rozšíří registrovanou projektovou bránu o backendové příkazy při zachování
frontend test/build. Worker externí registry/config neupravuje.

### Outputs a bezpečné získání klíče (pouze host)

Outputs obsahují URL `/v1`, FunctionName, RestApiId, ApiKeyId, UsagePlanId,
nikdy hodnotu API key. V privátním shellu vypnout tracing; nezapínat verbose curl,
nezapisovat klíč do souboru, historie, logů nebo dokumentace:

```sh
set +x
API_URL=$(aws cloudformation describe-stacks --stack-name wonderfulkb-case-client-mock --profile ai-hackathon --region eu-central-1 --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue | [0]' --output text)
API_KEY_ID=$(aws cloudformation describe-stacks --stack-name wonderfulkb-case-client-mock --profile ai-hackathon --region eu-central-1 --query 'Stacks[0].Outputs[?OutputKey==`ApiKeyId`].OutputValue | [0]' --output text)
API_KEY=$(aws apigateway get-api-key --api-key "$API_KEY_ID" --include-value --profile ai-hackathon --region eu-central-1 --query value --output text)
```

### Smoke (pouze host, po deployi)

Následující shell helper posílá klíč přes stdin konfigurace curl, ne přes argv.
`-i` ukáže HTTP status a response hlavičky; úspěchy musí mít
`X-Data-Backend: mock`. Po vytvoření/vazbě klíče může gateway potřebovat krátkou
dobu na propagaci. Žádné POST → další GET jako
důkaz persistence; ta je ověřena pouze offline v jedné repository.

```sh
mock_request() {
  printf 'header = "x-api-key: %s"\n' "$API_KEY" | curl --config - --silent --show-error -i "$@"
}
mock_request "$API_URL/clients"                                                # 200
mock_request "$API_URL/cases/fixture-old"                                      # 200, packaged fixture
mock_request "$API_URL/clients/11111111-1111-4111-8111-111111111111/cases"         # 200
mock_request -H 'Content-Type: application/json' -X POST "$API_URL/cases" \
  --data "{\"client_id\":\"11111111-1111-4111-8111-111111111111\",\"metadata\":{\"demo\":true}}" # 201
mock_request -H 'Content-Type: application/json' -X POST "$API_URL/cases" \
  --data '{"client_id":"33333333-3333-4333-8333-333333333333"}' # 409
mock_request -H 'Content-Type: application/json' -X POST "$API_URL/cases" \
  --data '{"client_id":"99999999-9999-4999-8999-999999999999"}' # 404
curl --silent --show-error -i "$API_URL/clients"                                # 403
curl --silent --show-error -i -H 'x-api-key: deliberately-invalid' "$API_URL/clients" # 403
unset API_KEY API_KEY_ID
unset -f mock_request
```

Ověřit i JSON `error` u 403; 429 má JSON gateway response při throttling/quota.
Skutečný runtime API key/gateway smoke je odpovědnost hosta, ne výsledek offline suite.

### Úklid pouze vytvořeného demo stacku (host)

```sh
sam delete --stack-name wonderfulkb-case-client-mock --profile ai-hackathon --region eu-central-1
unset API_URL
```

Tento postup se nevztahuje na jiné stacky/služby. Cloud deploy ani smoke nebyly
provedeny při lokální implementaci.
