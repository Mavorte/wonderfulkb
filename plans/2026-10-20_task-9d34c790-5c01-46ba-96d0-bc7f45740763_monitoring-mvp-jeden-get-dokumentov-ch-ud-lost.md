# Plan 2026-10-20: Monitoring MVP: jeden GET dokumentových událostí

Přidat jediný bounded document-events GET do existující intake; dodat guarded AWS test deployment a live ověření v témže tasku.

## Analysis

- `be-intake/app/main.py` má autentizaci přes `x-api-key`, `require_case` kontroluje pouze existenci případu a současný case/document klíč je `case_id, document_id`. Žádný ověřený trusted per-case authorization seam nebyl dosud doložen; před implementací ověřit skutečný seam, jinak zastavit zpřístupnění route a zaznamenat konkrétní blocker.
- Audit package poskytuje `AuditStore.read_document`, document-partition Query, stabilní `occurred_at,event_id` řazení, striktní event allowlist a scope-bound token. `audit_storage.read_document` předává chybu dál; API ji mapuje na 503, nikdy na úspěšnou prázdnou historii.
- Intake Dockerfile již wheel-buildí a instaluje interní `document_processing` package; ověřit finální artifact provenance/import v built image, nikoli předpokládat novou packaging cestu.
- `plans/monitoring/mvp-reference-20261019.md` stanoví MVP pagination, no-store a limity úplnosti. Společný YAML je výslovně jen čtený/ověřený vstup; jeho aktivní budoucí operace nejsou dodané endpointy.
- Důležité learnings: read chyby nejsou empty (`monitoring-filereceived-audit-store-scope.md`); raw DynamoDB Decimal integer fields vyžadují validovaný převod v `FileReceived.from_item` (`audit-envelope-decimal-round-trip.md`); nepředstírat producer, auth nebo live integraci, pokud chybí skutečné rozhraní.

## Approach

1. Prověřit skutečnou case authorization a case/document read seam, aktivní registration/gates a podporovaný deploy postup, target owner/revision, image provenance i existující config. Pokud authorization seam chybí, přesně popsat blocker bez auth frameworku/fallbacku a route nevystavit.
2. Implementovat sdílenou route facade `processing_monitor_routes.py` ve stávající FastAPI aplikaci a interní query/read vazbu pouze přes existující `AuditStore.read_document`. Validovat limit 1–100; vracet pouze event allowlist `items`, `next_token`, `observed_at`; řadit occurred_at,event_id. Zachovat `unknown`/neúplnou historii jako ne-business-failure a dokumentovat refresh od začátku bez late-event catch-up garance.
3. Udržet endpoint v přesném case/document scope: ověřit současný business key, 404 pro neexistující/cizí scope nebo již ověřenou konzistentní 403 policy. Přidat `Cache-Control: private, no-store` na úspěšné i chybné odpovědi; 503 pro nutný read-source failure; chyby nesmí logovat/vracet dokumentový obsah.
4. Zapojit router do `main.py`, zachovat auth middleware a ostatní routes. Přečíst jediný OpenAPI YAML a ověřit shodu route/DTO; neupravovat jej, nevytvářet druhý kontrakt a nepřidávat budoucí operace.
5. Spustit TDD focused testy a registrované gates. Poté zjistit aktuální existující AWS test App Runner target v eu-central-1, zachovat konfiguraci, před rolloutem uložit ověřený recovery artifact/config, použít revision/concurrency guard, doložit digest a bounded rollout completion. Po instalaci/deploy přímé autentizované HTTP ověření známého oprávněného syntetického case/documentu, continuation, schema, no-store a negativní auth/scope. Zapsat task evidence v `plans/monitoring/` bez secrets/document contents; fixture ID a write/request count uvést.
6. Použít jen existující bezpečnou synthetic fixture/cestu a minimální writes; žádný replay či ruční audit insert jako worker→HTTP důkaz. Rozlišit source/installed/deployed/live-function-verified; producer absence či oprávnění denial uvést jako konkrétní blocker. Při runtime-inaccessible deploymentu připravit artifact digest, target, config diff, recovery a přesný úzký operator krok pro Jackieho v rámci stejného tasku.

## Implementation

- První krok implementace: vytvořit focused testy a zachytit RED; následně přidat query response mapping, route, auth/scope integration, no-store/error mapping a router registration.
- Ověřit DynamoDB document scope pomocí `case_id, document_id`, nikoli historickým `pk/sk` business adapterem; audit reader smí používat svůj interní pk/sk pouze za existujícím `read_document` interface.
- Testy pokryjí FileReceived happy path, dvě stránky, cross-document token rejection, unauthenticated/unauthorized case, missing document, store error 503 a no-store včetně errors.
- Validovat jediný OpenAPI YAML proti jedinému dodávanému operation path/schema; budoucí operation definitions zůstanou pouze specifikací.
- Po testech/buildu ověřit target ownership/config/revision, recovery artifact, built image/package import, guardovaný deployment, skutečný image digest/revision, bounded health/rollout a přímé live route HTTP důkazy. Runtime error opravovat v rámci stejného scope a opakovat guardovaný rollout; rollback pouze proti vlastní revision/concurrency guard.
- Spustit registrovaný gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; Python focused testy dle TDD a odpovídající intake/audit package sadu.

## Testing

- Focused FastAPI tests: `cd be-intake && python3 -m pytest tests/test_processing_monitor_routes.py -q`.
- Package tests: `cd be-document-processing && .venv/bin/python -m pytest tests/test_monitor_audit_storage.py -q`.
- Contract validation: parse YAML and assert only that deployed operation/DTO matches `/cases/{case_id}/processing/documents/{document_id}/events`; do not edit YAML.
- Registered gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- Live acceptance: direct authenticated GET against discovered existing App Runner host and authorized synthetic scope; assert exact response keys/types, page continuation and cross-scope token rejection where fixture permits, `private, no-store` including failure responses, auth/scope statuses, deployed digest/revision. Hermetic store exception test covers 503; no cloud fault injection.
- Record exact safe statuses/assertions, fixture identifiers and write/request counts, source/artifact digest, target revision and deployment/recovery result in repo-local `plans/monitoring/` evidence. Do not claim live content verification if no legitimate producer event/fixture exists.

## TDD

Implement the TDD cycle using skill:tdd. Add `be-intake/tests/test_processing_monitor_routes.py` first, using the existing `intake` fixture from `test_monitor_file_received.py` (move/reuse fixture only if needed without duplicating application behavior).

**Run command:** `cd be-intake && python3 -m pytest tests/test_processing_monitor_routes.py -q`

```python
from fastapi.testclient import TestClient


def test_file_received_page_is_scoped_and_not_cacheable(intake):
    main, _, _, _, _, _ = intake
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/cases/case-test/processing/documents/doc-test/events",
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 200  # RED: route is not registered yet
    assert set(response.json()) == {"items", "next_token", "observed_at"}
    assert response.headers["cache-control"] == "private, no-store"
```

| Test | RED | GREEN |
|---|---|---|
| `test_file_received_page_is_scoped_and_not_cacheable` | Route returns 404 before registration | Returns bounded FileReceived DTO with no-store |
| Pagination/token scope | No endpoint/token handling | Page two resumes; other document token is rejected |
| Auth, case/document scope, read error | No route behavior | No auth denied; unauthorized/nonexistent scope follows verified policy; required store failure is 503 |

## Files

| Path | Planned change |
|---|---|
| `be-intake/app/processing_monitor_routes.py` | New thin API facade, shared scope/auth/no-store/error integration and DTO mapping, only if real authorization seam exists |
| `be-intake/app/main.py` | Register facade without changing existing service or package architecture |
| `be-document-processing/src/document_processing/audit/audit_queries.py` | Reuse/adjust the bounded audit query only if tests show the existing interface cannot satisfy current contract; no competing reader |
| `be-intake/tests/test_processing_monitor_routes.py` | TDD focused endpoint, pagination, token, auth/scope, error and cache tests |
| `plans/monitoring/<task-specific-evidence>.md` | Repo-local deployment/live evidence and concrete blocker if any; no secrets or document contents |
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | Read/validate only; ownership instructions prohibit modifying the shared contract in this task |

## Progress

- [x] Resolve canonical plan path and inspect project/task context.
- [x] Review audit query/store, intake routes/tests, package build, MVP guide and sole OpenAPI contract.
- [x] Recall relevant audit scope, Decimal round-trip and uncertainty learnings.
- [ ] Implementation agent: resolve trusted authorization seam and perform RED/GREEN implementation.
- [ ] Run focused tests, contract checks and registered test/build gate.
- [ ] Guarded AWS test deployment, live HTTP verification and repo-local evidence; report blockers truthfully.
