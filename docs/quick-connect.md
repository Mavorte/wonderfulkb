# wonderfulkb — DB & API quick-connect

Stav z 19. 10. 2026. Určeno pro lidi i agenty, kteří se potřebují rychle připojit.

**API klíč se do repozitáře nikdy nedává**. Je to klíč z AWS Secrets Manageru `wonderfulkb/ingest-api-key`
(stejný pro toto API i Ingest API); předávejte ho přes proměnnou prostředí:

```bash
export BASE=<AGENT_API_BASE_URL>
export KEY=...   # x-api-key, ne z repozitáře
```

## API (`wonderfulkb-agent-api`)

Jedna Lambda pro klienty, case i dokumenty. Kód [`be-validator-agent/api`](../be-validator-agent/api/README.md),
kontrakt [openapi-validator-agent.yaml](../be-document-processing/contracts/openapi-validator-agent.yaml).
Dřívější samostatné Case & Client API (`<CASE_API_ID>`, Lambda `wonderfulkb-case-client`) je od 19. 10. 2026 smazané.

| Route | Co dělá |
|---|---|
| `GET /clients?ico=12345678` | Přesné hledání podle IČO |
| `GET /clients?name=fiser&status=active&limit=50` | Filtr klientů, další stránky přes `next_token` |
| `GET /cases?limit=50` | Všechny case (Scan, pořadí není garantováno) |
| `POST /cases` | Založí case; služba vygeneruje UUIDv4 `case_id` |
| `GET /cases/{case_id}` | Detail case |
| `GET /clients/{client_id}/cases` | Case jednoho klienta, od nejnovějšího |
| `GET /cases/{case_id}/documents` | Dokumenty case včetně nahraných a ještě nezpracovaných (`queued`) |
| `GET /cases/{case_id}/documents/{document_id}` | Text, štítek, popis (`409`, dokud OCR nedoběhlo) |
| `…/vectors`, `…/signatures`, `…/signatures/{signature_id}/image` | Vektory, podpisy, odkrytí podpisu |

POST požadavek obsahuje `client_id` a případně `metadata` (JSON do 16 KiB). Každé volání vytvoří
nový case a vrací `201`; klientem dodané `case_id` se ignoruje. ID z odpovědi
slouží pro následné volání detailu. Nahrání dokumentů je v Ingest API ([be-intake](../be-intake/README.md)).

Sémantika chyb: chybějící API klíč → **401** · chybný API klíč → **403** · neznámý klient/case/dokument → **404** ·
klient `inactive`/`blocked` nebo nezpracovaný dokument → **409** · rate limit (10 req/s) → **429**.

## DynamoDB (ruční/debug přístup)

Tabulky: `wonderfulkb-uw-clients` (PK `client_id`, GSI `ico-index`),
`wonderfulkb-uw-cases` (PK `case_id`, GSI `client-created-index`), `wonderfulkb-uw-documents` (ingest),
`wonderfulkb-uw-document-analysis` (výsledky pipeline), `eu-central-1`.
Přístup používá IAM; přihlašovací údaje ani API klíče nepatří do repozitáře.
