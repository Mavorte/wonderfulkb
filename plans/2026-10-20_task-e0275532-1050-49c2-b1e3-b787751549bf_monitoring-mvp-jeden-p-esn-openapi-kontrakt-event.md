# Plan 2026-10-20: Monitoring MVP observation contract

Zúžit jediný monitor OpenAPI YAML na schválené bounded observations a jediný lifecycle read scope; dodat offline kontraktový důkaz bez routeru či deploymentu.

## Analysis

- `be-document-processing/contracts/openapi-processing-monitor.yaml` má nyní široké business, audit, artifact a list/detail operace; například `/processing/documents`, `/audit` a artifact paths přesahují požadovaný kontrakt.
- Proposal `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a briefs `plans/tasks/2026-10-19_monitor-mvp-03-document-events-get.md`, `...07-run-events-get.md`, `...09-attempts-get.md`, `...11-attempt-steps-get.md`, `2026-10-20_monitor-mvp-{13-attempt-pages-get,15-cache-reused-read,17-extraction-read,19-signature-read,21-publication-read,24-lifecycle-read}.md` určují požadované read surface; event typy vycházejí z briefs 06,08,10,12,14,16,18,20,22 a reducer 23.
- Brief 24 omezuje lifecycle scope na bounded runs, run detail a document audit; brief 23 vyžaduje partial evidence a neodvozování celohistorického stavu. Brief 17 říká, že tento kontrakt zůstává jediný zdroj pravdy, nikoli nasazovací důkaz.
- Stávající offline testovací styl je pytest (`be-document-processing/tests/test_monitor_audit_storage.py`); projektový `pyproject.toml` nastavuje testy do `tests`. Znovu použít pouze již nainstalované YAML parser/validator závislosti.
- Relevantní learning: `learnings/architecture/2026-10-19_monitoring-filereceived-audit-plan-scope.md` vymezuje FileReceived bez implikace dalších scope/deploy oprávnění; zachovat jej bez run_id.

## Approach

- Nejprve přidat focused pytest kontraktový test a ověřit skutečný RED proti současnému širokému dokumentu.
- Zredukovat YAML na pouze dokumentové events, run-events, pozorované AttemptStarted attempts, steps, pages a přesně tři bounded lifecycle operace z briefu 24. Každá kolekce má `items`, `next_token`, `observed_at`; požadované partial views deklarují `coverage=partial`.
- Přesně popsat jeden bounded observation window, limit 1–100, explicitní run/attempt scope, operation-bound opaque last-evaluated token včetně empty-items continuation; žádné snapshot/incremental/complete/latest garance, totals ani celohistorické agregace.
- Ponechat událostní enum a per-type field allowlists; zakázat content/raw errors/S3 keys/artifact-content paths. PageCompleted/PageFailed jsou jediná page terminal observations; cache reuse není inference; publication sama run neukončuje. Lifecycle unknown/ambiguous/partial bez syntetických starts, attempts či statuses; FileReceived nemá run scope.
- Vyjádřit skutečnou case authorization jako závislost interface: shared API key není case permission. Pokud trusted identity→case interface nelze doložit, označit konkrétně nedostupný interface. Popsat 400/403/404 dle doložitelné politiky, 503 pro required-read failure a private,no-store včetně chyb; žádný nový auth framework.

## Implementation

1. Zkontrolovat přesné briefy a proposal pro deset požadovaných operací a sémantiku eventů; nepřenášet staré širší endpointy ani jejich modely.
2. Vytvořit `be-document-processing/tests/test_monitor_openapi_observation_contract.py` s YAML parse, resolve refs, allowlist paths/parametrů/schema a negativními assertions pro širší business/artifact kontrakt; spustit cíleně a zachytit RED.
3. Upravit pouze `be-document-processing/contracts/openapi-processing-monitor.yaml`: paths, operations, reusable parameters/schemas/responses, descriptions a examples; držet OpenAPI 3.x a všechny `$ref` resolvable.
4. Spustit cílený test pro GREEN, následně registrované gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; zaznamenat, že jde o repo-local contract proof, bez route/deploy/live claim.

## Testing

- YAML syntaktické načtení a OpenAPI reference resolution offline.
- Přesný allowlist path/method: document events, run events, observed attempts, steps, pages, a pouze lifecycle runs/run-detail/document-audit dle briefu 24.
- Assert required fields, limit 1–100, explicit scopes, operation-bound continuation semantics, `coverage=partial`, empty items with next token, private/no-store and required error statuses.
- Assert schema allowlists/no content fields, raw errors, S3 keys, artifact/content paths, unrequested business run lists/details and no snapshot/totals/full-history guarantees.
- Spustit focused `pytest be-document-processing/tests/test_monitor_openapi_observation_contract.py` z `be-document-processing/`, poté registrovaný backoffice test/build gate.

## TDD

Implementace TDD cyklu dle skill:tdd.

**Test file:** `be-document-processing/tests/test_monitor_openapi_observation_contract.py`  
**Framework:** pytest; použít dostupný YAML parser a případnou dostupnou OpenAPI resolver knihovnu, bez nové dependency.  
**Run command:** `pytest tests/test_monitor_openapi_observation_contract.py` (cwd `be-document-processing`).

```python
from pathlib import Path

import yaml


CONTRACT = Path(__file__).parents[1] / "contracts" / "openapi-processing-monitor.yaml"


def test_only_approved_observation_paths_are_published():
    document = yaml.safe_load(CONTRACT.read_text())
    assert set(document["paths"]) == {
        "/cases/{case_id}/processing/documents/{document_id}/events",
        "/cases/{case_id}/processing/documents/{document_id}/runs/{run_id}/events",
        "/cases/{case_id}/processing/documents/{document_id}/runs/{run_id}/attempts",
        "/cases/{case_id}/processing/documents/{document_id}/runs/{run_id}/steps",
        "/cases/{case_id}/processing/documents/{document_id}/runs/{run_id}/pages",
        "/cases/{case_id}/processing/documents/{document_id}/runs",
        "/cases/{case_id}/processing/documents/{document_id}/runs/{run_id}",
        "/cases/{case_id}/processing/documents/{document_id}/audit",
    }  # RED: current YAML includes broad document and artifact operations.
```

| Test assertion | RED | GREEN |
|---|---|---|
| Approved path allowlist | Fails on current extra paths | Exact eight approved paths only |
| References and observation schema | Fails on absent/incorrect required bounded fields | All refs resolve; items, next_token, observed_at and required partial coverage are present |
| No content/business projections | Fails on artifact paths or broad DTOs | No prohibited content, raw errors, S3 keys, totals, or unrequested paths |
| Scope, continuation and security semantics | Fails on missing assertions/description requirements | Explicit scopes, bounds, opaque tokens, 503 and private,no-store contract hold |

## Files

| File | Change |
|---|---|
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | Replace broad contract with approved observation-only paths and precise schemas/semantics. |
| `be-document-processing/tests/test_monitor_openapi_observation_contract.py` | Add offline parser, refs, path, parameter and schema assertions. |
| `plans/2026-10-20_task-e0275532-1050-49c2-b1e3-b787751549bf_monitoring-mvp-jeden-p-esn-openapi-kontrakt-event.md` | Plan/progress record at canonical task path. |
| `learnings/architecture/` | Save at least one relevant session learning after completing the main work, per task instruction. |

## Progress

- [x] Canonical plan path obtained and project contract/test context inspected.
- [x] Locate authoritative proposal, briefs 03/07/09/11/13/15/17/19/21/24, event/reducer references and existing focused-test pattern.
- [ ] During implementation, confirm exact type-to-fields requirements and implement contract-test RED, YAML update, GREEN and registered gate.
- [ ] Save session learning after the implementation task and record its verification; this planning task does not execute implementation or tests.
