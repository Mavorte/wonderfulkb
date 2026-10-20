# trigger: automatické spuštění pipeline po nahrání dokumentu

Řeší nález **B1** z [validator-agent-audit.md](../../../be-validator-agent/docs/validator-agent-audit.md): po uploadu přes ingest nic nespustilo pipeline, nový případ neměl řádek v analýze a agent API vracelo 404. **Stav: připraveno, NENASAZENO** (nasazení a zapnutí streamu schvaluje uživatel).

```
ingest (App Runner)           DynamoDB wonderfulkb-uw-documents
 PDF -> S3, pak 1 transakce ──▶ INSERT nového řádku ──▶ Stream (NEW_IMAGE, filtr jen INSERT)
                                                          │
                                       Lambda wonderfulkb-trigger-enqueue
                                       analysis řádek `queued` (podmíněný zápis) + zpráva do SQS
                                                          ▼
                              SQS wonderfulkb-trigger-documents ──(3× selže)──▶ DLQ ──▶ Lambda wonderfulkb-trigger-dlq
                                       │ batch 1, nejvýš 2 souběžně                    řádek `failed` + důvod + metrika
                                       ▼
                         Lambda wonderfulkb-trigger-worker (kontejnerový image, 900 s)
                         claim řádku → pipeline.run_document → řádek completed / partial / failed
                         poslední dokument případu ──▶ zpráva `case` ──▶ pipeline.copies.copy_case (copy_suspicion)
                                                                          ──▶ webhook Wonderful → case `evaluating`
```

**Stav případu** (`wonderfulkb-uw-cases`, [case-statuses.md](../../architecture/case-statuses.md)): enqueue po zařazení dokumentu nastaví `intake_in_progress` (jen z `open` nebo `awaiting_clarification`, best effort: chyba nezdrží dokument, jen metrika `CaseStatusFailed`). Případový krok po kontrole kopií zavolá webhook Wonderful (`wonderful_webhook.py`, URL a `X-Webhook-Secret` ze secretu `wonderfulkb/wonderful-webhook` jako JSON `{"url", "secret"}`, parametr `WonderfulWebhookSecretName`; prázdný = vypnuto) a teprve po odpovědi 2xx nastaví `evaluating`. Obojí jen dokud je případ `open` nebo `intake_in_progress`, takže opakovaná zpráva `case` druhou evaluaci nespustí. Selhání webhooku vrátí zprávu do fronty (stav se nemění). Selhání kontroly kopií evaluaci nezdrží. Ostatní stavy nastavuje Wonderful přes `PUT /cases/{case_id}/status`.

Kdo co dělá: **enqueue** (jen zápis řádku a zpráva, bez AWS volání mimo DynamoDB a SQS), **worker** (jediný, kdo volá Bedrock a Textract), **DLQ obsluha** (označí řádek `failed`, aby agent API vrátilo `failed`, ne věčné `queued`).

## Proč právě takhle (porovnání spouštěčů)

| Varianta | Dopad na sdílený bucket a ingest | Rizika | Verdikt |
|---|---|---|---|
| **DynamoDB Stream na `wonderfulkb-uw-documents`, jen INSERT** | žádný na bucket, žádná změna kódu ingestu; změna tabulky je jedna vlastnost šablony bez přerušení a bez nahrazení | stream jde zapnout až po nasazení šablony tabulky; existující řádky ve streamu nejsou (řeší `backfill.py`) | **vybráno** |
| S3 událost na `wonderfulkb-raw-document-storage` | bucket je sdílený a má jen jednu konfiguraci notifikací; zápis (`put-bucket-notification-configuration`) přepíše cizí, EventBridge by se zapnulo pro celý bucket a hlásilo i `analysis/`, `pages/`, `vision/` | událost přijde dřív než řádek v tabulce dokumentů (ingest píše PDF jako první, řádek až v transakci) → worker by narazil na neznámý dokument; duplicitní upload téhož obsahu přepíše objekt a spustí znovu | zamítnuto |
| Odeslání do SQS z ingestu | změna kódu a nový image App Runneru, ingest by záviselo na dostupnosti SQS (nebo by musel zprávu ztratit) | zpráva před commitem transakce by mohla předběhnout řádek, po commitu může odeslání selhat → dokument bez zpracování | zamítnuto |

Stream vidí přesně to, co chceme: řádek vznikne **až po** uložení PDF a v jedné transakci s ostatními dokumenty nahrání; duplicitní nahrání nic nezapíše, takže nic nespustí. Stream je zdarma pro Lambdu a neovlivní zápisy ingestu.

## Rozhodnutí a odchylky od zadání

- **Souběžnost 2 se omezuje na event source mappingu (`ScalingConfig.MaximumConcurrency`), ne rezervovanou souběžností.** Účet má celkem 10 souběžných provedení (`get-account-settings`: ConcurrentExecutions 10, Unreserved 10) a AWS vyžaduje nechat nerezervovaných aspoň 10, takže `ReservedConcurrentExecutions: 2` by nasazení odmítlo. Mapování omezuje počet souběžných workerů na 2 a zprávy navíc nechává ve frontě (bez chyb).
- **Worker je kontejnerový image, ne zip.** Závislosti (PyMuPDF s ONNX runtime, numpy, Pillow, pypdfium2, pypdf, cryptography) mají po rozbalení **325 MB** (změřeno `pip install --target` s koly pro Linux, Python 3.14), limit zipu je 250 MB. Enqueue a DLQ obsluha jsou malé zipy (jen `trigger/`, boto3 z runtime).
- **Paměť 3008 MB** (zadání 3 až 10 GB): účty bez zvýšené kvóty mají nejvyšší paměť 3008 MB; `WorkerMemory` jde zvýšit parametrem. Architektura worker image je x86_64 (image se staví na stejné architektuře, bez emulace).
- **Limit Bedrocku:** sdílí ho celý tým (50/min). Každý worker dostane `BedrockRpm` (výchozí 12) pro každou z komponent vision/classify/embed (v dokumentu běží za sebou), dva workery tedy nejvýš ~24 požadavků za minutu. Nastavuje se přes proměnné `PIPELINE_BEDROCK_RPM`, `CLASSIFY_MAX_RPM`, `WONDERFULKB_BEDROCK_RPM`. Omezovače hlídají jen svůj proces; ostatní sessions týmu limit využívají zvlášť.
- **Případová část** nepíšu znovu: volá se `pipeline.copies.copy_case` (jiná session ji napsala nad `signature_pipeline.copycheck.mark_copies`). Worker spouští pipeline s `Options(defer_copy_check=True)`, takže se porovnání **nepočítá po každém dokumentu**, ale jednou za případ po dokončení posledního dokumentu (zpráva typu `case`). Pozdější nový dokument téhož případu ji spustí znovu; `copy_case` je idempotentní.
- **Soukromí podpisů (rozhodnutí 19. 10.):** worker běží s `PIPELINE_REDACT=1` (výchozí v pipeline, v šabloně uvedené výslovně): pipeline zamaskuje podpisové oblasti v paměti, zamaskovanou kopii zapíše do `cases/<case>/redacted/<document_id>.pdf` a dál čte jen ji, výřezy šifruje (`PRIVACY_KMS_KEY_ID`). Proto je parametr `SignatureKmsKeyArn` **povinný** (`deploy.sh` ho zjistí z aliasu `alias/wonderfulkb-signatures` jen čtením) a role workeru má `kms:GenerateDataKey` a `kms:DescribeKey` s podmínkou kontextu (`case_id`, `document_id`, `signature_id`), **bez `kms:Decrypt`** (odkrývat smí jen API). Worker smí `GetObject` z `original/`, ale **nesmí do `original/` zapisovat**; zapisuje jen `redacted/` a `analysis/`.
- **Atribut navíc v řádku analýzy:** `failure_reason` (S, jen u selhání a opakování; pipeline řádek při úspěchu přepíše celý, takže zmizí). `pipeline_version` je u řádku založeného triggerem `pending`, dokud ho nepřepíše pipeline. API ani kontrakt tím nejsou dotčeny (čtou jmenované atributy); do `be-validator-agent/docs/validator-agent-storage.md` jsem nesahal, doplnit je na uživateli.

## Chování a idempotence

Stav je jediný, řádek v `wonderfulkb-uw-document-analysis`; SQS i stream jsou at-least-once, proto je každý krok podmíněný zápis.

| Situace | Co se stane |
|---|---|
| nový dokument (stream INSERT) | podmíněné založení řádku `queued` (`attribute_not_exists`), pak zpráva. Zpráva je až za řádkem: když odeslání selže, stream zkusí znovu a `queued` řádek zprávu stále pošle (zpráva se tedy může zdvojit, nikdy neztratit) |
| duplicitní nahrání téhož souboru | ingest nic nezapíše → žádný záznam ve streamu → nic se nespustí |
| zpráva pro `completed` dokument | worker ho přeskočí (nic nevolá, řádek ani S3 nemění); jen `"force": true` (backfill `--force --case`) ho spustí znovu |
| zpráva přijde dvakrát současně | `claim`: podmíněný zápis `queued/failed/partial → processing` uspěje jen jednou, druhá zpráva končí jako „busy“ bez práce |
| worker spadl nebo vypršel čas (900 s) | řádek zůstane `processing`; claim je po 930 s mrtvý (`LEASE_SECONDS`, kratší než viditelnost fronty 1200 s), takže opakování ho převezme |
| výjimka ve workeru | claim se uvolní (`queued`), důvod se zapíše do `failure_reason`, zpráva se vrátí do fronty; max 3 pokusy |
| 3. selhání | zpráva do DLQ → obsluha DLQ označí řádek `failed` (`PROCESSING_GAVE_UP`, nebo důvod z workeru), pošle metriku `DeadLettered`; DLQ se tím vyprazdňuje, znovu zařadit lze `backfill.py` |
| poškozená zpráva (nejde JSON, jiná verze, špatné id, `..`) | worker ji pošle rovnou do DLQ s atributem `reason` a vrátí úspěch (bez tří zbytečných pokusů); metrika `MalformedMessage` |
| dokument není v tabulce dokumentů | zpráva se zahodí (metrika `UnknownDocument`), řádek se nezakládá |
| `run_document` skončí `failed` (rozbité PDF, chybějící originál) nebo `partial` | je to konečný stav, bez opakování (opakování by nic nezměnilo); znovu až `backfill.py --statuses failed,partial` |

**Případový krok.** Po každém dokumentu worker zkontroluje, zda jsou všechny dokumenty případu v konečném stavu (`completed/partial/failed`, konzistentní čtení). Jakmile ano, pošle jednu zprávu `case`; tu zpracuje `copy_case` (znovu vyřízne podpisy z originálů podle uložených detekcí, bez Textractu a Bedrocku, a přepíše jen pole `copy_suspicion` v `signatures.json`). Dva dokumenty dokončené najednou mohou poslat zprávu dvakrát; výsledek je stejný.

## Soubory

| Soubor | Obsah |
|---|---|
| `template.yaml` | SAM šablona stacku `wonderfulkb-trigger`: 2 fronty, 3 Lambdy, 3 role, 3 log skupiny, 3 alarmy |
| `documents-table-with-stream.yaml` | nezávislá kopie `infra/documents-table/template.yaml` se zapnutým streamem (původní nezměněna) |
| `ecr.yaml` | repozitář `wonderfulkb-trigger-worker` (stack `wonderfulkb-trigger-ecr`) |
| `common.py`, `enqueue_handler.py`, `worker_handler.py`, `dlq_handler.py`, `case_step.py` | kód Lambd (balíček `trigger`) |
| `backfill.py` | zařazení dokumentů bez `completed` řádku do fronty |
| `build.sh`, `Dockerfile` | složí balíčky v `build/` ze sourozeneckých modulů (pipeline, classify, embed, dedup, signature_pipeline, signature_privacy) (čtou se, nic se v nich nemění) |
| `deploy.sh` | `--plan`, `stream`, `trigger`, `rollback` |
| `scripts/e2e_check.sh` | po nasazení: jeden nový unikátní dokument pod případem `trigger-test-<čas>` přes ingest → `queued` → `completed`, pak duplicitní upload (nic nespustí); nic nemaže |
| `tests/` | testy nad moto, bez AWS |

## Změna tabulky `wonderfulkb-uw-documents` (zapnutí streamu)

Rozdíl proti `infra/documents-table/template.yaml` (jediný):

```diff
+      StreamSpecification:
+        StreamViewType: NEW_IMAGE
+
+Outputs:
+  StreamArn:
+    Value: !GetAtt DocumentsTable.StreamArn
```

CloudFormation to provede bez přerušení a bez nahrazení tabulky (`StreamSpecification` je „No interruption“); klíče, data, tag stacku `project=wonderfulkb` zůstávají. `deploy.sh stream` nejdřív vytvoří change set, ukáže ho (Replacement musí být `False`) a čeká na potvrzení. Alternativa bez změny šablony: `aws dynamodb update-table --table-name wonderfulkb-uw-documents --stream-specification StreamEnabled=true,StreamViewType=NEW_IMAGE`; stack pak má drift a při pozdější aktualizaci ze staré šablony se stream vypne, proto doporučuji změnu šablony. Do původní šablony jsem nepsal, rozhodne uživatel, zda ji přepíše kopií.

## Nasazení

```bash
cd infra/validator-agent/trigger
aws sso login --profile hackathon
./deploy.sh --plan        # jen čtení: kontroly, co se vytvoří, odhad backfillu (nic se nevytvoří ani nestaví)
./deploy.sh stream        # krok 1: zapne stream (change set + potvrzení "enable-stream")
./deploy.sh trigger       # krok 2: ECR, image, stack (potvrzení "deploy-trigger"; pak ještě change set SAM)
python3 backfill.py                   # suchý běh: kolik dokumentů a jakých stavů
python3 backfill.py --apply           # zařadí je (30 zpráv za minutu); zpracování řídí workery
```

Potřebuje: `sam` a `cfn-lint` (`python3 -m venv .venv-lint && .venv-lint/bin/pip install -r requirements-lint.txt`), Docker, profil `hackathon`; testy a `backfill.py` `.venv` (`python3 -m venv .venv && .venv/bin/pip install --only-binary :all: -r requirements-dev.txt`). Volitelné proměnné pro `./deploy.sh trigger`: `MaxConcurrency`, `BedrockRpm`, `WorkerMemory`, `AlarmTopicArn` (SNS pro alarmy). Klíč KMS se bere z aliasu `alias/wonderfulkb-signatures` (čtení).

Sestavení bere sourozenecké moduly tak, jak leží na disku (`pipeline/`, `classify/`, `embed/`, `signatures/signature_pipeline`, `privacy/signature_privacy`); jiná session je dál mění, proto `deploy.sh trigger` staví hned před nasazením a po změně pipeline je potřeba spustit ho znovu.

Backfill: `--case X`, `--statuses missing,failed,partial,queued,processing` (výchozí všechny; `processing` jen mrtvý claim), `--max N`, `--rate` (zpráv/min), `--force --case X` (spustí znovu i `completed`). `completed` nikdy nemění. Dokumenty řadí po případech, takže se případy dokončují postupně a případový krok běží brzy.

## Zpět

`./deploy.sh rollback` (potvrzení `rollback`): smaže stack `wonderfulkb-trigger`, stack `wonderfulkb-trigger-ecr` (repozitář i s image) a vrátí stack tabulky na původní šablonu (stream se vypne). Tabulky a objekty v S3 se nemění; řádky ve stavu `queued` zůstanou a jdou zařadit později. Rychlé zastavení bez mazání: v konzoli nebo `aws lambda update-event-source-mapping --uuid <uuid> --no-enabled` pro mapování fronty (workery se zastaví, zprávy zůstanou ve frontě 4 dny).

## Alarmy a metriky

Alarmy: `wonderfulkb-trigger-dead-lettered` (metrika `wonderfulkb/Trigger` `DeadLettered`, emitovaná jako EMF log obsluhou DLQ), `wonderfulkb-trigger-dlq-not-empty` (zprávy v DLQ, které obsluha nezvládla) a `wonderfulkb-trigger-queue-stuck` (nejstarší zpráva čeká > 4 h). Bez `AlarmTopicArn` jen mění stav. Další metriky: `MalformedMessage`, `UnknownDocument`, `BadStreamRecord`.

## IAM (nejmenší práva)

Tři role, každá jen na své zdroje: **enqueue** čte stream a zapisuje/čte analýzu a posílá do dvou front; **DLQ obsluha** čte DLQ, aktualizuje řádky, čte seznam dokumentů a posílá `case` zprávu; **worker** čte tabulku dokumentů, zapisuje analýzu, čte `cases/*/original/*`, `cases/*/redacted/*` a `cases/*/analysis/*`, zapisuje jen `cases/*/redacted/*` a `cases/*/analysis/*` (do `original/` ne), `s3:ListBucket` jen s prefixem `cases/*` (bez něj vrací chybějící klíč 403 místo 404; kopie podpisů listuje prefixy případu), index hashů obsahu (`wonderfulkb-uw-content-hashes`: Get/Put/Update/Query, modul dedup), S3 Vectors (Put/Get/Query/List/Delete) jen na tři indexy, `bedrock:InvokeModel` jen na Titan text v2, Titan image v1 a profil Claude Haiku 4.5, `bedrock-mantle:CreateInference` jen pro model Qwen3 VL, `textract:AnalyzeDocument` (bez omezení zdroje, jak AWS vyžaduje) a KMS jen `GenerateDataKey`/`DescribeKey` na jeden klíč s podmínkou kontextu. Žádné `*` v akcích; `*` ve zdroji jen pro Textract a `dynamodb:ListStreams` (test v `tests/test_template.py`).

## Odhad nákladů (z paměti, ceny neověřené)

Worker: 3 GB × ~60 s na dokument ≈ 0,003 USD, backfill ~140 dokumentů ≈ 0,5 USD Lambda. Dominují stejně jako dosud volání pipeline: Textract podpisy (~3,5 USD za 1000 stran, 140 dokumentů ≈ 600 až 1200 stran → 2 až 4 USD), Titan embedding a klasifikace Haiku v řádu desítek centů. SQS, stream (čtení Lambdou zdarma), DynamoDB on-demand, logy (14 dní): pod 1 USD. ECR: pět image po ~0,6 GB ≈ 0,3 USD měsíčně. Celý backfill zhruba **3 až 6 USD** a při 12 požadavcích/min na worker zhruba **1 až 1,5 h** (dva workery, ~1100 volání Titanu pro ~560 stran). Nový dokument: asi 0,03 až 0,05 USD, minuty od uploadu.

## Testy

```bash
cd infra/validator-agent/trigger && python3 -m venv .venv && .venv/bin/pip install --only-binary :all: -r requirements-dev.txt
.venv/bin/python -m pytest              # 63 testů (včetně tvaru šablony), bez AWS (moto)
```

Pokrytí: stream → řádek `queued` a zpráva, jen INSERT, přeskočení `completed`/běžícího, převzetí mrtvého claimu, opakovaná doručení, uvolnění claimu po výjimce, 10 tvarů poškozené zprávy (rovnou do DLQ), neznámý dokument, DLQ obsluha (důvod, `completed` se nepřepíše, zprávy mimo schéma), případová zpráva po posledním dokumentu (i po `failed`), `backfill.py` (suchý běh, filtry, závod s dokončením, `--force`), **celá cesta s opravdovým `pipeline.run_document`** (textové PDF, rozbité PDF, chybějící originál, duplicitní doručení nezapíše znovu) a **opravdové `pipeline.copies.copy_case`** nad třemi PDF (stejný podpis ve dvou → `suspected`, jiný → `none`, druhé spuštění nic nemění). Šablony: `cfn-lint` a `sam validate --lint` bez chyb, tvar (štítky, názvy, `VisibilityTimeout` > timeout, bez rezervované souběžnosti, filtr INSERT, žádné `*` akce).

## Ověřeno a neověřeno

Ověřeno: testy výše; `cfn-lint` 1.53 a `sam validate --lint` (SAM CLI 1.169) čisté; `./deploy.sh --plan` proti účtu (jen čtení, výstup v odpovědi session); změna tabulky je rozdíl o jedné vlastnosti proti šabloně, která sedí na nasazenou (porovnáno v `--plan`).

**Neověřeno / rizika:**
- **Nic z toho neběželo v AWS.** Stream, mapování, IAM podmínky (hlavně `bedrock-mantle:Model` a profil Haiku) a skutečné limity se ukážou až při nasazení; první dokument sledujte v logu `/aws/lambda/wonderfulkb-trigger-worker`.
- **Čas nejdelšího dokumentu** (19 stran, ~260 s při ~22 požadavcích/min podle pilotu pipeline) při 12 požadavcích/min vychází na ~300 až 380 s (38 volání Titanu, 190 až 380 s samotné čekání omezovače + Textract + klasifikace), tedy pod 900 s; **živě jsem to neměřil**. Bez stropu stran v pipeline (audit D2) ale dokument nad ~70 stran při 12 požadavcích/min 900 s nestihne (2 volání Titanu na stranu) a skončí třemi timeouty v DLQ jako `failed`.
- Image se staví a spouští v lokálním Lambda runtime kontejneru proti moto (výsledek v sekci níže); proti skutečné Bedrock/Textract/S3 Vectors ne.
- **Maskování a KMS živě neověřeno z workeru:** podmínka `kms:EncryptionContextKeys` a práva `GenerateDataKey`/`DescribeKey` jsou převzaté z `be-validator-agent/docs/validator-agent-privacy.md` část 7 a vyzkoušené jen tam (`live_check.py` pod jinou rolí). Maskování přidává ke každému dokumentu detekci Textractem na originále, redakci a `verify_redacted`; čas na dokument jsem s ním neměřil (odhad 300 až 380 s u 19 stran je bez něj). Pokud `verify_redacted` selže, dokument skončí `failed` a worker ho neopakuje.
- Index hashů `wonderfulkb-uw-content-hashes` (dedup) jsem v AWS nezkoumal; worker má jen práva, tabulku nezakládá.
- Pořadí ESM na DLQ: obsluha DLQ maže zprávy po označení řádku, dohledání příčiny je z logů `wonderfulkb-trigger-worker` (14 dní) a z `failure_reason`.
- Rozlišení „dokument čeká na nasazený worker“ a „dokument nikdy nebude zpracován“ dělá až alarm `queue-stuck` (4 h).

## Návrh bucket policy (jen text, nezapsáno, nic se nenasazuje)

Bucket `wonderfulkb-raw-document-storage` dnes nemá bucket policy (viz privacy doc, část 1). Pokud uživatel chce, aby čitelný originál četl jen worker, ingest a správce, a aby `redacted/` psal jen worker, stačí tato policy; **neaplikovat bez rozhodnutí**, protože zablokuje všechny ostatní čtenáře `original/` (`be-document-processing`, případné nástroje Wonderful), dokud se jim `s3_key` nepřepne na `redacted/`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "ReadOriginalsOnlyWorkerIngestAdmin", "Effect": "Deny", "Principal": "*", "Action": "s3:GetObject",
     "Resource": "arn:aws:s3:::wonderfulkb-raw-document-storage/cases/*/original/*",
     "Condition": {"ArnNotLike": {"aws:PrincipalArn": [
       "arn:aws:iam::<ACCOUNT_ID>:role/wonderfulkb-trigger-worker",
       "arn:aws:iam::<ACCOUNT_ID>:role/wonderfulkb-ingest-instance",
       "arn:aws:iam::<ACCOUNT_ID>:role/aws-reserved/sso.amazonaws.com/*/AWSReservedSSO_ai-hackathon-TeamAdmin_*"]}}},
    {"Sid": "WriteMaskedCopiesOnlyWorkerAdmin", "Effect": "Deny", "Principal": "*",
     "Action": ["s3:PutObject", "s3:DeleteObject"],
     "Resource": "arn:aws:s3:::wonderfulkb-raw-document-storage/cases/*/redacted/*",
     "Condition": {"ArnNotLike": {"aws:PrincipalArn": [
       "arn:aws:iam::<ACCOUNT_ID>:role/wonderfulkb-trigger-worker",
       "arn:aws:iam::<ACCOUNT_ID>:role/aws-reserved/sso.amazonaws.com/*/AWSReservedSSO_ai-hackathon-TeamAdmin_*"]}}}
  ]
}
```

Poznámky: výslovné `Deny` platí i pro role s právy v IAM; roli správce je nutné ponechat, jinak se nikdo nedostane k originálům; ručně spouštěná pipeline (`python -m pipeline` pod SSO rolí) spadá pod správce. Ověřit `ArnNotLike` s `aws-reserved/sso.amazonaws.com/<region>/` v ARN před použitím.

## Požadavky na jiné části (nepsal jsem tam)

- **pipeline/** (strop stran, audit D2): `run_document` nemá strop počtu stran; pro Lambdu s limitem 15 minut je potřeba (např. 60 stran → `partial` s `pages_failed`), jinak velký PDF tři hodiny blokuje worker a končí v DLQ.
- **pipeline/** (stav `partial`, audit P2): API nerozlišuje `partial` kvůli stranám a kvůli embedu/klasifikaci; worker to nemění.
- **be-validator-agent/docs/validator-agent-storage.md:** doplnit atribut `failure_reason` a `pipeline_version: pending` u řádku založeného triggerem; do `docs/wonderful-validator-agent.md` stav `queued` už není jen po ručním `run_case`.
- **infra/documents-table/template.yaml:** přepsat kopií se streamem, až uživatel schválí krok 1 (jinak další nasazení té šablony stream nevypne, ale stack se rozejde s repozitářem).
- **signatures/ / privacy/:** worker image obsahuje `signature_privacy`, PyMuPDF a `cryptography` (maskování je zapnuté vždy).
