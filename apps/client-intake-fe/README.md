# Client Intake

Client-facing intake page. The client opens a share link, sees their case and client details, and uploads PDFs, which are passed on to the AWS ingest service.

## Flow

1. Link: `https://kb-hackathon.app.sb.wonderful.ai/s/G2o9x5js40Ir?h=<hash>` (the app's anonymous share link; no access token)
2. `functions/intake-get` maps `h` → `case_id` in table `client_intake.intake_links`, calls `GET /cases/{case_id}` and the client lookup on the case/client API, and returns case, client and whether upload is available.
3. The browser sends each PDF (base64, max 10 MB) to `functions/intake-stage`, which stores it in Custom Storage under `client-intake/<case_id>/<uuid>/<name>` and returns the key. A share-link app can only invoke Functions, not the Custom Storage API.
4. The browser calls `functions/intake-submit` with `h` and the storage keys plus original file names. The function checks the keys are inside the case's folder, downloads the files, POSTs them in one `multipart/form-data` request to `{kb_aws_ingest_url}/cases/{case_id}/documents`, and deletes the storage copies once ingest accepts them.

The API keys stay server-side (`fetch(..., { secretName })`), so the AWS services need no CORS.

## Configuration

| Name | Kind | Value |
| --- | --- | --- |
| `kb_aws_documents_api_url` | global variable | API base (klienti, case, dokumenty), `<AGENT_API_BASE_URL>`. Empty → mock data. |
| `kb_aws_ingest_url` | global variable | Ingest service base, `https://vt9mavpjky.eu-central-1.awsapprunner.com/v1`. Empty → upload disabled. |
| `kb-aws-ingest-api-key` | secret, type API Key | Key for both the case/client API and ingest (AWS Secrets Manager `wonderfulkb/ingest-api-key`): `{"header_name": "x-api-key", "api_key": "..."}` |

Case details shown come from `case.metadata` (`loan_number`, `asset`, `serial_number`, `required_documents` string array), falling back to the top-level `loan_agreement_no`, `asset_name` and `serial_number` that synthetic cases use. `GET /clients/{client_id}` is not deployed, so the function falls back to `GET /clients?ico=<metadata.ico>`, or lists the clients and matches `client_id`.

## Links

Add a row per case (`hash` is the primary key; use a random, unguessable value):

```sh
wful --profile kb-hackathon tables row-insert --table client_intake.intake_links \
  --set hash=$(python3 -c "import secrets;print(secrets.token_urlsafe(16))") --set case_id=<case_id>
```

Then send the client the app's anonymous share link with `?h=<hash>`:

```
https://kb-hackathon.app.sb.wonderful.ai/s/G2o9x5js40Ir?h=<hash>
```

The share link needs anonymous access to stay enabled for the app, and the anonymous audience must be allowed to call `intake-get`. The share page creates its own session on each visit, so there is no token to mint or swap into the link.
