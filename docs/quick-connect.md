# wonderfulkb — DB & API quick-connect

Stav z 19. 10. 2026 (převzato ze Slacku). Určeno pro lidi i agenty, kteří se potřebují rychle připojit.

**API klíč se do repozitáře nikdy nedává**. Klíč získejte od týmu a předávejte ho přes proměnnou prostředí:

```bash
export BASE=https://bgm7k1ggqi.execute-api.eu-central-1.amazonaws.com/v1
export KEY=...   # x-api-key, ne z repozitáře
```

## Public API (case-client)

| Route | Co dělá |
|---|---|
| `GET /clients?ico=12345678` | Přesné hledání podle IČO |
| `GET /clients?name=fiser&status=active&limit=50` | Filtr klientů, další stránky přes `next_token` |
| `POST /cases` | Založí case; služba vygeneruje UUIDv4 `case_id` |
| `GET /cases/{case_id}` | Strong-read detail case |
| `GET /clients/{client_id}/cases` | Cases jednoho klienta |

POST požadavek obsahuje `client_id` a případně `metadata`. Každé volání vytvoří
nový case a vrací `201`; klientem dodané `case_id` se ignoruje. ID z odpovědi
slouží pro následné volání detailu.

> **Nasazený stav ověřený 19. 10. 2026:** deployed POST stále vyžaduje `case_id`
> a používá idempotentní chování. Tento stav je historická provozní poznámka,
> nikoli důkaz ani odraz aktuálního zdrojového handleru. Source kontrakt OpenAPI
> 1.4.0 generuje UUID na serveru; nasazení nové verze je samostatná fáze.

Sémantika chyb: chybný API klíč → **403** · neznámý klient/case → **404** · klient `inactive`/`blocked` → **409** · rate limit → **429**.

## DynamoDB (ruční/debug přístup)

Tabulky: `wonderfulkb-uw-clients` (PK `client_id`, GSI `ico-index`),
`wonderfulkb-uw-cases` (PK `case_id`, GSI `client-created-index`), `eu-central-1`.
Přístup používá IAM; přihlašovací údaje ani API klíče nepatří do repozitáře.

Související: [OpenAPI](../be-case-client/openapi-case-client.yaml),
[Case Client README](../be-case-client/README.md).
