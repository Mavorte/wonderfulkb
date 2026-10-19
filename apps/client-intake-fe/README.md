# Client Intake

Client-facing intake page. The client opens a share link, sees their case and client details, and uploads PDFs straight to the AWS ingest service.

## Flow

1. Link: `https://kb-hackathon.app.sb.wonderful.ai/app-view/?access_token=<token>&h=<hash>`
2. `functions/intake-get` maps `h` → `case_id` in table `client_intake.intake_links`, calls `GET /cases/{case_id}` and `GET /clients/{client_id}` on the case/client API, and returns case, client and upload target.
3. The browser POSTs all files in one `multipart/form-data` request to `{kb_aws_ingest_url}/cases/{case_id}/documents` with `x-api-key`.

## Configuration

| Name | Kind | Value |
| --- | --- | --- |
| `kb_aws_case_api_url` | global variable | Case/client API base, e.g. `https://<apiId>.execute-api.eu-central-1.amazonaws.com/v1`. Empty → mock data. |
| `kb_aws_ingest_url` | global variable | Ingest service base. Empty → upload disabled. |
| `kb-aws-api-key` | secret, type API Key | `{"header_name": "x-api-key", "api_key": "..."}` |

The AWS ingest service must allow CORS from `https://kb-hackathon.app.sb.wonderful.ai` (`POST`, headers `x-api-key`, `Content-Type`, plus the `OPTIONS` preflight).

Case details shown come from `case.metadata`: `loan_number`, `asset`, `serial_number`, `required_documents` (string array). Until `GET /clients/{client_id}` exists, the function falls back to `GET /clients?ico=<metadata.ico>`.

## Links

Add a row per case (`hash` is the primary key; use a random, unguessable value):

```sh
wful --profile kb-hackathon tables row-insert --table client_intake.intake_links \
  --set hash=$(python3 -c "import secrets;print(secrets.token_urlsafe(16))") --set case_id=<case_id>
```

Mint the access token (max 24 h, valid for every case) and append `&h=<hash>`:

```sh
wful --profile kb-hackathon call post /api/v2/apps/37d42bc0-d2bb-4205-9d28-1829c64a4862/asset-session --data '{"expires_in": 86400}'
```
