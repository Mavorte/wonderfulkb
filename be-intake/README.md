# Ingest API (`wonderfulkb-ingest`): nahrávání dokumentů, pro Wonderful

Stav: **služba běží na App Runner; adresu a API klíč dostanete od nás.** Formální popis: [openapi-ingest.yaml](openapi-ingest.yaml). Navazuje na API případů ([openapi-validator-agent.yaml](../be-document-processing/contracts/openapi-validator-agent.yaml), `POST /cases`): case musí existovat (zakládá se přes `POST /cases`).

- Base URL: `<UPLOAD_URL>` (tvar `https://<id>.<region>.awsapprunner.com/v1`, všechny cesty níže jsou pod `/v1`). **Je to jiná adresa než u API případů a dokumentů (`wonderfulkb-agent-api`).** Upload běží jako samostatný kontejner, protože API Gateway a Lambda by 4–5 MB soubory nezvládly s rezervou.
- Autentizace upload/list: hlavička `x-api-key: <klíč>`. **Je to stejný klíč jako u API případů a dokumentů (`wonderfulkb-agent-api`)**, jeden klíč pro obě služby. Monitoring `/processing/documents/.../events` má samostatnou SERVICE Bearer autorizaci popsanou níže. Klíče kontroluje služba, ne API Gateway; patří pouze na backend.
- Kontrola dostupnosti: `GET /healthz` (bez `/v1`, bez klíče) vrací `200 {"status": "ok"}`.
- Formát: nahrání je `multipart/form-data`, ostatní odpovědi jsou JSON (UTF-8), časy v ISO 8601 (UTC).
- Chyby: `{"error": "popis"}` s kódem 400 (špatný požadavek, např. chybí `files`, neplatné `case_id`, parametr mimo rozsah), 401 (chybí klíč), 403 (špatný klíč), 404 (case neexistuje), 413 (moc velké), 415 (není PDF), 5xx (zkuste znovu). Kód 429 tu není, služba nemá usage plán. Klíč se kontroluje před čtením těla, takže bez platného klíče se nic nenahraje.
- Limity: až 20 souborů na volání, 25 MB na soubor, 100 MB všech souborů dohromady v jednom požadavku.

## 1. Nahrání dokumentů
`POST /cases/{case_id}/documents`, `Content-Type: multipart/form-data`

| Pole | Povinné | Popis |
|---|---|---|
| `files` | ano | PDF. Pole se opakuje, jedna část na soubor. `filename` části je původní název souboru. |
| `uploaded_by` | ne | Kdo dokumenty nahrál (do auditu), max 255 znaků, např. `reviewer@kb.cz`. |

```bash
curl -X POST "$UPLOAD_URL/cases/170170-25/documents" -H "x-api-key: $API_KEY" \
  -F uploaded_by=reviewer@kb.cz \
  -F files=@0_Form_Smlouva.pdf \
  -F files=@01_Form_VOP.pdf
```
Odpověď `201 Created`:
```json
{ "case_id": "170170-25",
  "documents": [
    { "document_id": "7d0c5f1e-3a52-5c0e-9b3c-1f6a8e2d4b90", "filename": "0_Form_Smlouva.pdf",
      "received_at": "2026-10-19T14:15:00Z", "content_type": "application/pdf",
      "size_bytes": 412331, "duplicate": false } ] }
```
- **`document_id`** je zároveň `blob_id`. Počítá se z `case_id` a SHA-256 obsahu, takže stejný soubor ve stejném case má vždy stejné `document_id`. Hodnoty v příkladech jsou jen ilustrace.
- **Duplicity:** stejný obsah v témže case se znovu nezapíše, vrátí se původní `document_id` a `duplicate: true`. Opakování volání je tedy bezpečné.
- **Všechno, nebo nic:** nejdřív se zkontrolují všechny části. Je-li jedna špatná (neplatný typ, moc velká), nezapíše se žádná a odpověď je chyba. Záznamy nových dokumentů se pak zapisují jednou transakcí, takže case uvidí všechny nově nahrané dokumenty, nebo žádný. Skončí-li volání chybou 5xx, zopakujte ho beze změny; stejné soubory se nezdvojí. Stejný soubor dvakrát v jednom volání se uloží jednou, druhý výskyt má `duplicate: true`.
- **Typ:** jen PDF, skeny také. Kontroluje se hlavička souboru `%PDF-`, ne jen `Content-Type` části. Jiný typ vrátí `415`.
- `404`: `case_id` neexistuje (zjistí se hned, před čtením těla, takže špatné volání nestojí celý upload). `413`: soubor je větší než 25 MB nebo součet souborů přesahuje 100 MB (je-li v požadavku `Content-Length` o víc než 1 MB nad 100 MB, služba ho odmítne hned, bez čtení těla). `400`: chybí `files`, je jich víc než 20, `uploaded_by` má přes 255 znaků nebo je neplatné `case_id` (1 až 128 znaků `A-Z a-z 0-9 . _ -`). `415`: soubor nezačíná `%PDF-`, tedy i prázdný soubor.
- Soubory se ukládají do dočasného souboru a odtud streamují do S3, nedrží se celé v paměti. Request timeout App Runneru je asi 120 s, velké nahrání musí v tomto čase doběhnout.
- Odpověď obsahuje u každého dokumentu `duplicate`; `uploaded_by` se v odpovědi na nahrání nevrací, vrací se až ve výpisu.

## 2. Výpis dokumentů case
`GET /cases/{case_id}/documents?limit=50&next_token=…&with_urls=true`

Všechny parametry jsou volitelné. Řazeno podle času přijetí (`received_at`, vzestupně). `limit` je výchozí 50, 1 až 100 (jinak `400`). `next_token` je v odpovědi vždy, při poslední stránce `null`; jinak ho pošlete beze změny v dalším volání pro další stránku (je to zakódovaný offset, berte ho jako neprůhlivou hodnotu; neplatný token vrátí `400`). `with_urls=true` přidá ke každému dokumentu `download_url`, předpodepsaný odkaz platný 5 minut (300 s). `uploaded_by` je v dokumentu jen tehdy, byl-li zadán. Case bez dokumentů vrací `200` s prázdným polem.
```json
{ "case_id": "170170-25",
  "documents": [
    { "document_id": "7d0c5f1e-3a52-5c0e-9b3c-1f6a8e2d4b90", "filename": "0_Form_Smlouva.pdf",
      "received_at": "2026-10-19T14:15:00Z", "content_type": "application/pdf",
      "size_bytes": 412331, "uploaded_by": "reviewer@kb.cz",
      "download_url": "https://…" } ],
  "next_token": null }
```
`download_url` nikam neukládejte, po 5 minutách přestane platit. Další odkaz získáte novým voláním s `with_urls=true`.

## Doporučený postup
1. Založit case (`wonderfulkb-agent-api`, `POST /cases`) a zapamatovat si `case_id`.
2. Nahrát všechna PDF případu jedním voláním `POST /cases/{case_id}/documents`.
3. Při chybě sítě nebo 5xx zopakovat stejné volání, duplicity se nezapíšou dvakrát.
4. Nahrané dokumenty zobrazit uživateli přes `GET /cases/{case_id}/documents`.

## Co zatím neplatí
- Adresu a klíč vám předáme my, nejsou součástí repozitáře ani dokumentace.
- Mazání dokumentů a stav jejich zpracování přijdou později.

## Lokální build image

Z kořene repozitáře (build context zahrnuje interní Python package):

```bash
docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:filereceived-local .
```

Image instaluje wheel `wonderfulkb-document-processing` bez worker dependencies;
audit používá intake boto3/botocore. `AUDIT_TABLE_NAME` zapíná best-effort
FileReceived po úspěšném S3 + metadata commitu; prázdná hodnota jej vypíná.
Build/import a konfigurační kontrakt: [file-received-build-contract.md](../plans/monitoring/file-received-build-contract.md).
## Document-events SERVICE authorization

`GET /v1/cases/{case_id}/processing/documents/{document_id}/events` accepts a
server-only `Authorization: Bearer <credential>` over HTTPS. Upload API keys,
browser claims, case existence and continuation tokens never grant monitoring
access. The monitoring credential grants no upload/list access.

Set `PROCESSING_MONITOR_AUTHORIZATION_SECRET_ARN` to the dedicated eu-central-1
Secrets Manager ARN and use that same ARN for the existing `MonitorAuthSecretArn`
template parameter. Its optional IAM statement grants only GetSecretValue on
that exact ARN; it does not change the upload secret or its policy. This is an
ARN reference in ordinary App Runner environment configuration, not an injected
secret value: AWSCURRENT is read anew on every monitoring request.

The versioned server-owned JSON is:

```json
{
  "version": 1,
  "credentials": [{"sha256": "<64 lowercase hex SHA-256>", "principal_id": "monitor-synthetic"}],
  "principals": [{"id": "monitor-synthetic", "type": "SERVICE", "enabled": true,
                  "case_ids": ["explicit-existing-synthetic-case-id"]}],
  "retained_documents": []
}
```

Generate raw credentials with a cryptographically secure generator using at
least 32 random bytes (256 bits). Store only digests in this policy. Deliver the
raw credential only via the existing secure operator channel; never put it,
policy contents or credential digests in deployment evidence. Provision only
the explicitly approved existing synthetic case; empty grants revoke access,
and wildcards, duplicate bindings and malformed entries are rejected.

Membership is checked with a strongly consistent exact case/document GetItem;
no case business row is required. Only when that document row is absent may an
exact retained record establish membership:
`{"case_id":"...","document_id":"...","source_revision":"verified-commit-reference","verified_at":"2026-10-20T10:00:00Z"}`.
The operator must derive this record from previously verified committed
metadata and retain its real source revision/verification provenance. A guessed
key or an audit event is not evidence. A read failure never falls back to this
record, and the current case grant is still mandatory.

Rotation: add a second digest bound to the same principal, securely switch the
caller and verify it, then remove the old digest. Revoke by removing a digest,
disabling the principal or removing its case grant. Use an idempotency token and
expected old VersionId when moving AWSCURRENT; abort on version drift. No
process restart or last-known-good authorization cache is involved.

Responses always carry `Cache-Control: private, no-store`. Missing/forged identity
or revoked/ungranted case returns 403 before membership/audit I/O; unknown or
foreign document 404; invalid scope/limit/cursor 400; required authorization,
membership, audit configuration/read/decoding failure 503. Empty history is 200
only after successful authorization, membership and a successful bounded read.
The DTO is `{items,next_token,observed_at,coverage}` with `coverage: partial`.
Limit is 1–100 (default 50); tokens are document/operation-bound, max 4096 chars.

**Unresolved contract gate:** the existing one-Query reader continues in
`EVENT#event_id` order. It is neither a snapshot nor a globally chronological
timeline; sorting individual pages cannot make it chronological. The proposal's
`occurred_at,event_id` requirement has not been waived. This implementation does
not claim chronological acceptance or deployed/live success pending resolution
by the contract owner. Refresh begins from the first page; late inserts may be
missed during an old continuation.

For AWS TEST delivery, inspect current ownership/revision/config and fixture
processing routing first. Retain a verified recovery image/config, acquire the
execution lock, recheck revision/config immediately before mutation, preserve
all unrelated configuration and deploy the verified immutable artifact via the
existing owner procedure. Verify the actual deployed digest and bounded
upload→post-commit FileReceived→GET tuple. Do not upload until the existing
fixture's no-provider path has been verified. Task-local evidence and budgets:
`plans/monitoring/task-cf441015-6bba-4862-8200-b2c0047f6905-http-evidence.md`.

### Existing lifecycle policy compatibility

The shared authorization module also normalizes the existing lifecycle policy
below into the same credential/grant/membership checks. Legacy document grants
remain exact document allowlists. `MONITOR_AUTH_SECRET_ARN` is a fallback only
when the new ARN is unset; configuring both selects the new policy for all
monitoring authorization. Lifecycle routes retain their additional intake-key
guard. They reuse the shared adapter and do not implement another secret reader.

The lifecycle HTTP routes require both the existing `x-api-key` and an additional
server-only `Authorization: Bearer <monitoring credential>` header over HTTPS.
Do not send this credential to browsers or log either header. Client principal
claims and cursor contents never grant access.

Configure `MONITOR_AUTH_SECRET_ARN` on the App Runner service and pass that same
ARN as the `MonitorAuthSecretArn` CloudFormation parameter. The instance role
gets only `secretsmanager:GetSecretValue` on that exact secret. Preserve all
existing environment variables, secret references and instance configuration
when updating App Runner. `AUDIT_TABLE_NAME` binds the bounded read table as well
as the independent fail-open upload audit writer.

The dedicated secret's `AWSCURRENT` JSON schema is:

```json
{
  "schema_version": 1,
  "credentials": [{
    "credential_id": "monitor-v1",
    "sha256": "<64 lowercase hex SHA-256 of the bearer credential>",
    "state": "active",
    "principal_type": "SERVICE",
    "principal_id": "monitor-synthetic",
    "grants": [{
      "case_id": "synthetic-case-id",
      "documents": [{"document_id": "synthetic-document-id", "membership": "current"}]
    }]
  }]
}
```

Use a cryptographically random credential. The placeholder digest above must be
replaced. IDs are exact opaque IDs, never wildcards. Current membership is checked
with a consistent document GetItem after the explicit grant check. Retained
audit-only membership uses `membership: retained` and an additional server-owned
`provenance` object with exact keys `record_id`, `verified_by`, `verified_at`
(UTC ISO timestamp). An operator must verify the original case/document ownership
before issuing this retained record; audit rows are not membership evidence.
Do not grant real business documents to synthetic test credentials.

Each request retrieves and validates the current secret with bounded SDK timeouts
and one attempt; there is no stale grant fallback. The shared adapter fails
closed before audit reads. The legacy lifecycle facade retains its own public
error mapping; the document-events status contract is specified above.

For rotation, retain the prior recoverable secret version securely, read the
current VersionId, create a candidate version with an explicit idempotency token,
and move AWSCURRENT with the expected old version (`RemoveFromVersionId`) as a
concurrency guard. During a bounded overlap the policy may list two distinct
active credential versions. Verify the new version through an entitled read,
then mark the old credential `revoked` in a guarded successor version. Read back
VersionId and verify the next request using the old credential is denied. Never
put raw credentials or policy bodies in deployment evidence. Abort on version or
service-revision drift; preserve recovery material outside the repository.

### Run event observations

`GET /v1/cases/{case_id}/processing/documents/{document_id}/runs/{run_id}/events`
uses the same authorization, membership, reader and safe event DTO as document
events. `limit` (1–100, default 50) bounds evaluated document events, not matching
run events. Exactly one document Query is performed; no Scan or fill-page loop.
FileReceived without run identity and other runs are excluded. Empty `items` can
have a `next_token`; an unobserved run is not declared nonexistent. Every response
has `coverage: partial`, UTC `observed_at`, and `Cache-Control: private, no-store`.
The opaque token (maximum 8192 characters) binds operation/case/document/run and
resumes from the last evaluated event position. Invalid/cross-scope cursors are
400; each continuation repeats current authorization (403) and membership (404).
Read/decoder/DTO failures are 503. Technical `EVENT#event_id` ordering is neither
global chronology nor a snapshot; this endpoint makes no completeness claim.

### Attempt observations

`GET /v1/cases/{case_id}/processing/documents/{document_id}/runs/{run_id}/attempts`
uses that same authorization/membership and single bounded document Query. Only
stored `AttemptStarted` observations for the requested run are exposed as
`{event_id, attempt_no, occurred_at}`; no observed `RunQueued` is required.
Distinct event IDs with equal attempt numbers stay separate observations, not a
business-state conclusion. No total, status or attempt duration is inferred.
The collection retains `coverage: partial`, UTC `observed_at`, nullable
`next_token`, and private/no-store semantics. Limit defaults to 50 (1–100), and an
empty evaluated page may have continuation. Tokens bind the attempts operation
as well as case/document/run; document-events and run-events tokens cannot be
reused here. Technical event-identity ordering and refresh/replay provide neither
chronology nor snapshot/completeness guarantees. Missing document is 404;
authorization/read failures follow the shared 403/503 policy.
