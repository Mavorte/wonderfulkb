# wonderfulkb — DB & API quick-connect

Stav z 19. 10. 2026 (převzato ze Slacku). Určeno pro lidi i agenty, kteří se potřebují rychle připojit.

**API klíč se do repozitáře nikdy nedává** (repozitář je veřejný). Klíč získejte od týmu, případně ze Secrets Manageru `wonderfulkb/ingest-api-key`, a předávejte ho přes proměnnou prostředí:

```bash
export BASE=https://bgm7k1ggqi.execute-api.eu-central-1.amazonaws.com/v1
export KEY=...   # x-api-key, ne z repozitáře
```

## Public API (case-client, část 1 — běží)

| Route | Co dělá | Příklad |
|---|---|---|
| `GET /clients?ico=12345678` | přesné hledání podle IČO | `wget -qO- --header "x-api-key: $KEY" "$BASE/clients?ico=12345678"` |
| `GET /clients?name=fiser&status=active&limit=50` | filtr podle části názvu a stavu, stránka 50 klientů, dál přes `next_token` | stejně s těmito parametry |
| `POST /cases` | založí case: `{client_id, metadata?}`, **`case_id` přidělí služba** | viz níže |
| `GET /cases/{case_id}` | detail case | `$BASE/cases/<case_id>` |
| `GET /clients/{client_id}/cases` | case jednoho klienta, nejnovější první | `$BASE/clients/<uuid>/cases` |

```bash
wget -qO- --header "x-api-key: $KEY" --header "Content-Type: application/json" \
  --post-data '{"client_id":"a3d1c2e4-5b6f-4a7d-8e9f-0a1b2c3d4e5f"}' "$BASE/cases"
```

Odpověď `201` obsahuje přidělené `case_id` (UUID); použijte ho v dalších voláních (`GET /cases/{case_id}`, `POST /cases/{case_id}/documents`).

> **Pozor na rozdíl oproti nasazené verzi.** Verze nasazená v době zápisu ještě vyžaduje `case_id` v těle `POST /cases` a je idempotentní (stejné `case_id` + `client_id` → `200`, kolize s jiným klientem → `409`). Kontrakt v tomto repozitáři (OpenAPI 1.4.0) už `case_id` nevyžaduje, generuje ho služba a každé volání založí nový case. Do nasazení nové Lambdy platí starý popis.

Sémantika chyb: chybějící nebo špatný klíč → **403** · neznámý klient/case → **404** · klient `inactive`/`blocked` → **409** · nad 10 req/s (burst 20) → **429**.

Data: zatím 1 syntetický klient (IČO 12345678) + 1 case; plná seed data nejsou nahraná (plánováno).

## DynamoDB (ruční/debug přístup)

Tabulky: `wonderfulkb-uw-clients` (PK `client_id`, GSI `ico-index`), `wonderfulkb-uw-cases` (PK `case_id`, GSI `client-created-index`). On-demand, `eu-central-1`. Žádná hesla ani databázový port: každé volání je HTTPS podepsané IAM (stačí naše SSO session).

```bash
aws dynamodb get-item --region eu-central-1 --profile "$AWS_PROFILE" \
  --table-name wonderfulkb-uw-clients \
  --key '{"client_id": {"S": "a3d1c2e4-5b6f-4a7d-8e9f-0a1b2c3d4e5f"}}'
```

Pro vlastní dotazy do tabulek je potřeba `dynamodb:GetItem/Query/Scan` na obě tabulky a jejich indexy (případně si vyžádejte roli). **Žádné IP whitelisty**, přepnutí sítě přístup nerozbije.

Související: [openapi-case-client.yaml](../be-case-client/openapi-case-client.yaml), [wonderful-ingest.md](wonderful-ingest.md) (část 2, upload PDF).
