# Case Explorer

Internal test console for the KB hackathon. It shows what is in the AWS tables, read through the APIs rather than DynamoDB directly, and starts the case-evaluator agent for a case ID.

- **Clients** (left): `GET /clients`, filtered by name or IČO (an 8-digit query is treated as an IČO). The panel collapses to a narrow rail; the choice is remembered in `localStorage`.
- **Client**: details, then `GET /clients/{client_id}/cases`.
- **Case**: `GET /cases/{case_id}`, then the documents API `GET /cases/{case_id}/documents`. A document opens in three views: text (`/documents/{id}`), vectors and signatures.
- **Evaluations** (under the case): the case's rows in `agent_functions.case_evaluations` and `agent_functions.case_evaluation_results`, read from the tables directly. **Delete all** removes every row of both tables for that case, after a confirmation. Click a run to see only its results: they come from `evaluation-results`, polled every 3 s while the run is selected, with a green blinking **Live** dot. Polling stops when the run is unselected (click it again or ×), the case is closed or changed, or another client is picked. The tables belong to the `agent-functions` app and are linked to this one.
- **Run evaluator**: the header box (or the case card) POSTs `{"payload": {"case_id": "..."}}` to the case-evaluator webhook trigger `062b5032-a738-48c9-810e-b726788add38`.

Every panel shows the upstream HTTP status, URL and key used; **Raw** shows the response body as is.

## Functions

All `POST`, called as `case-explorer/<slug>`. Each returns `{ url, status, ok, body, secret?, error? }` with HTTP 200, so the app shows upstream errors instead of throwing.

| Function | Body | Upstream |
| --- | --- | --- |
| `clients-list` | `ico?`, `name?`, `status?`, `next_token?` | `GET /clients` |
| `client-cases` | `client_id`, `next_token?` | `GET /clients/{client_id}/cases` |
| `case-get` | `case_id` | `GET /cases/{case_id}` |
| `documents-list` | `case_id`, `next_token?` | documents API `GET /cases/{case_id}/documents` |
| `document-get` | `case_id`, `document_id`, `view` (`validation`, `vectors`, `signatures`) | documents API |
| `evaluator-run` | `case_id` | case-evaluator webhook |
| `evaluations-list` | `case_id` | `agent_functions.case_evaluations` and `case_evaluation_results`, filtered by `case_id` |
| `evaluation-results` | `evaluation_id` | One run's row in `case_evaluations` and its rows in `case_evaluation_results` |
| `evaluations-delete` | `case_id` | Deletes the case's rows: results first, then runs. Returns the counts. |

## Configuration

| Name | Kind | Value |
| --- | --- | --- |
| `case_eval_documents_api_url` | global | AWS API serving cases, clients and documents, `https://rzt8s2u0p6.execute-api.eu-central-1.amazonaws.com/v1` (API Gateway `wonderfulkb-agent-api`; `openapi-case-client.yaml`, `documents_for_agent_api.json`). |
| `kb-aws-ingest-api-key` | secret | Key for that API. |
| `case_eval_webhook_secret` | secret (API Key, header `X-Webhook-Secret`) | Secret of the webhook trigger above, created for this app. |

## Checks

```sh
pnpm install && pnpm typecheck && pnpm build    # functions
cd app && pnpm install && pnpm build            # app
```
