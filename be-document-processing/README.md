# wonderfulkb – dokumenty, OCR a vytěžení firemních údajů

Implementace přijímá PDF, PNG a JPEG do 25 MiB a 50 stran. Dokument je vždy navázaný na existující `case_id`; `client_id` určuje server podle případu. OCR, vytěžení a kontroly konzistence jsou oddělené kroky. Originální přepis se při normalizaci ani ruční opravě nepřepisuje.

## AWS Bedrock – pouze Frankfurt

Inference i AWS úložiště jsou konfigurované do **eu-central-1**. Jiný `BEDROCK_REGION` aplikace odmítne. Neprovádí se automatický regionální fallback ani použití globálního inference profilu.

Výchozí model: **Qwen3 VL 235B A22B**, na endpointu Mantle s ID `qwen.qwen3-vl-235b-a22b-instruct`. Požadavky na `https://bedrock-mantle.eu-central-1.api.aws/v1/chat/completions` se podepisují IAM SigV4 službou `bedrock-mantle`, včetně dočasného session tokenu. Samostatný klíč poskytovatele modelu není potřeba.

Alternativně `google.gemma-4-31b`; adaptér automaticky použije jeho odlišnou cestu `/openai/v1/chat/completions`. `mistral.ministral-3-14b-instruct` je další konfigurovatelný kandidát; dostupnost v konkrétním účtu je potřeba ověřit. Modely nemají mezi sebou automatický fallback.

**Haiku:** podle dokumentace AWS ověřené 19. 10. 2026 nemá [Haiku 4.5](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-haiku-4-5.html) ani [Haiku 5.5](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-haiku-5-5.html) přímou In-Region inferenci ve Frankfurtu. EU inference profil může požadavky směrovat do dalších evropských regionů. Starší Claude 3 Haiku ve Frankfurtu [dosáhl EOL 10. 9. 2026](https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle-legacy.html). Pro požadavek výhradně Frankfurt proto Haiku není nakonfigurovaný.

Výchozí režim `auto` nejdříve zkusí **po jednotlivých stránkách přečíst PDF pomocí PyMuPDF**, včetně textových bloků a jejich pozic. Použitelný viditelný text předá LLM k následnému vytěžení. Prázdná/krátká, špatně kódovaná, skrytá textová vrstva nebo převaha rastrového skenu znamená fallback na **vykreslenou stránku v Bedrock vision LLM**. Díky tomu fungují i smíšená PDF. Režim `visual` vynutí vizuální přepis každé stránky. Obrázky vždy procházejí vizuálním přepisem. Následuje samostatná LLM extrakce nad přepisem a kontrola citací, hodnot a rolí. Text dokumentu je nedůvěryhodný vstup, ne instrukce pro model.

VLM neposkytuje ověřenou lokalizaci ani kalibrovanou jistotu: tento adaptér vrací `bbox: null` a `confidence: null`. Výsledky lze dohledat podle stránky, identifikátoru bloku a citace. Podpisy a razítka jsou pozorování modelu; pravost se neposuzuje. Neplatný JSON nebo zkrácená odpověď není úspěšné OCR.

Nativní PDF větev vrací pozice textových bloků z PyMuPDF; tabulky a vizuální značky samostatně neanalyzuje. Textová vrstva se heuristicky prověřuje, nikoli kryptograficky nebo vizuálně ověřuje. Pro čtení razítek, podpisů a kontrolu vůči skutečnému vzhledu stránky použijte `visual`.

## Lokální spuštění s Bedrockem

```bash
cd be-document-processing
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export PYTHONPATH=src
export AWS_PROFILE=ai-hackathon
export AWS_DEFAULT_REGION=eu-central-1
export OCR_PROVIDER=bedrock
export BEDROCK_REGION=eu-central-1
export BEDROCK_API=mantle
export BEDROCK_OCR_MODEL=qwen.qwen3-vl-235b-a22b-instruct
export BEDROCK_EXTRACTION_MODEL=qwen.qwen3-vl-235b-a22b-instruct
aws sso login --profile ai-hackathon
.venv/bin/uvicorn document_processing.api:create_app --factory --host 127.0.0.1 --port 8010
```

Profil nejdříve nastavte přes `aws configure sso`, pokud ještě neexistuje. V konzoli Bedrock ve Frankfurtu ověřte dostupnost modelu pro svůj účet. Dokumenty se do Bedrocku posílají až při zpracování úlohy. Spuštění integračních testů Bedrock nevolá.

Bez cloudové inference lze pro testování použít `OCR_PROVIDER=local` a režim `auto`. Volitelné offline OCR obrázků vyžaduje `pip install -r requirements-local-ocr.txt` (RapidOCR jako srovnávací baseline, ne specializovaný český model). Produkční návrh používá Bedrock; tento lokální baseline režim není automatický fallback při výpadku AWS.

Lokální server používá SQLite, soubory a obnovitelný worker. Poskytuje také vývojovou implementaci klientského API se třemi syntetickými firmami a ukládáním případů. Cloudová dokumentová služba čte existující tabulky klientů a případů a tyto endpointy nevystavuje.

## API a kontrakty

**Návrh monitorovacího čtecího API (nenasazeno):** [contracts/openapi-processing-monitor.yaml](contracts/openapi-processing-monitor.yaml), [průvodce rozhraním](PROCESSING-MONITOR-API.md) a [proposal](../docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md). Odděluje čtení dnešního AWS upload/analysis od zápisu budoucích runtime událostí (revize 0.3.0): audit business entity nekopíruje, běhy/pokusy/kroky jsou odvozené pohledy; aktuální AWS schéma má přednost před starším adapterem. Návrh nepřidává novou aplikaci ani nemění business data. Následující popis existujícího source API není důkazem shody s nasazeným runtime.

Interaktivní dokumentace: `http://127.0.0.1:8010/docs`. Strojové kontrakty jsou v `contracts/`. Kontrakt čtecího API pro vyhodnocovacího (validačního) agenta Wonderful, tj. dokumenty, vektory a podpisy, je v `contracts/openapi-validator-agent.yaml` a popsaný v [VALIDATOR-AGENT.md](VALIDATOR-AGENT.md) (návrh, zatím neimplementováno). V API Gateway stage `v1` odpovídá lokálnímu prefixu `/v1`.

1. `POST /v1/cases/{case_id}/documents` s `filename`, `content_type`, `size_bytes`, `mode` vrátí dokument a podepsaný upload.
2. Proveďte `PUT` souboru přes vrácenou URL a hlavičky.
3. `POST /v1/cases/{case_id}/documents/{document_id}/complete` vrátí 202 a `job_id`. Opakování je idempotentní.
4. `GET /v1/cases/{case_id}/documents` vrací průběh; `.../{document_id}/result` přepis, tabulky, pole a důkazy. Před vznikem výsledku vrací 409.
5. `GET .../{document_id}/pages/{page_number}` vrátí náhled stránky.
6. `POST .../{document_id}/corrections` s `run_id`, `field_id`, `normalized_value`, `reason` uloží auditovanou opravu vedle originálu.
7. `GET /v1/cases/{case_id}/validation` porovnává doložené hodnoty a vrací nálezy s odkazy na zdroje.

Stavy: `awaiting_upload`, `queued`, `processing`, `completed`, `partial`, `failed`. Stav případu `open` se tím nemění. Každá vstupní stránka zůstává ve výsledku i při chybě. Úspěšné stránky se při opakování úlohy načítají z cache; klíč zahrnuje verzi pipeline, modely, region a API. AWS zpracovává konkrétní verzi objektu S3 a ověřuje SHA-256.

Částky jsou desetinné řetězce s oddělenou měnou, IČO a účty řetězce. Normalizovaná data používají ISO 8601. Chybějící důkaz znamená nejisté pole, ne domyšlenou hodnotu. Ruční oprava má vlastní audit; při použití sdíleného API klíče identifikuje audit API klienta, nikoliv ověřenou fyzickou osobu.

Povinné typy dokumentů nastavte přes `case.metadata.required_document_types`. Bez profilu se úplnost označí jako nenakonfigurovaná. Peněžní rozdíly se porovnávají jen při doložené shodné měně a vrací se jako nálezy k prověření rozsahu plnění. Agregace více faktur pro více strojů vyžaduje doplnění vztahového modelu. Shoda údajů nepotvrzuje pravost dokumentu.

## AWS infrastruktura

`template.yaml`: API Gateway s API klíčem, ingest Lambda, worker Lambda, S3 s verzováním, DynamoDB pro metadata a fronta SQS s DLQ. IAM workeru omezuje inference na vybraný model, projekty v `eu-central-1` a tento region. Konkurence workerů je omezena na 2. Tabulky firem a případů se předávají názvem a musí existovat podle kontraktu `be-case-client/`.

```bash
sam build --use-container
sam deploy --guided --region eu-central-1 --profile ai-hackathon
```

Nasazení vytváří placené AWS prostředky. Šablona ani testy žádné nasazení samy neprovádějí. Prohlížeč nemá dostat API klíč; používá serverový proxy přístup. Lokálně se API klíč nastavuje přes `DOCUMENT_API_KEY`. Bez něj API **odmítá** požadavky na `/v1/` (503 `API_AUTH_NOT_CONFIGURED`); běh bez klíče je jen výslovný opt-in `DOCUMENT_API_ALLOW_NO_AUTH=1` pro lokální vývoj (je v `.env.example`). V cloudu klíč vynucuje API Gateway, proto šablona nastavuje Lambdě `DOCUMENT_API_ALLOW_NO_AUTH=1`. `AllowedOrigin` nastavte na skutečný původ backoffice kvůli přímému uploadu do S3.

## Ověření

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python scripts/export_contracts.py
```

Testy pokrývají podpis Mantle, výhradní použití Frankfurtu, rozdílné API cesty modelů, odmítnutí nedoložených údajů a rolí, idempotenci, izolaci případů, neměnné uploady, částečné výsledky, opakování úloh a historii ručních oprav.

PDF testy ověřují nativní text s pozicemi, následnou Bedrock extrakci, smíšené PDF, sken s digitálním zápatím, skrytý text, chybu Python extrakce a vynucený vizuální režim. AWS adaptéry se testují přes Moto, včetně připnutí verze S3 a odeslání SQS; nejde o test skutečné cloudové služby.

Pro měření OCR používejte pouze primární PDF syntetické sady. Anotace a čisté reference patří pouze evaluátoru. Měřte CER/WER včetně diakritiky, přesnou shodu identifikátorů a částek, role, tabulky, latenci a spotřebu. Dosavadní test vybraných výřezů není hodnocení celostránkového OCR. Živá kvalita a dostupnost Bedrocku nejsou ověřené offline testy.

Primární dokumentace: [Qwen3 VL](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-qwen-qwen3-vl-235b-a22b.html), [Gemma 4](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-google-gemma-4-31b.html), [endpointy](https://docs.aws.amazon.com/bedrock/latest/userguide/endpoints.html), [IAM Mantle](https://docs.aws.amazon.com/service-authorization/latest/reference/list_bedrock-mantle.html).
