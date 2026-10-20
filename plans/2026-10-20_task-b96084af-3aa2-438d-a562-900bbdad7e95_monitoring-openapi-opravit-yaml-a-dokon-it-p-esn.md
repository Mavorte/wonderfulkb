# Plan 2026-10-20: Monitoring OpenAPI observation DTO kontrakty

Dokončit jediný OpenAPI YAML a jeho focused contract test; žádné runtime route změny ani deployment.

## Analysis

- Aktuální YAML `be-document-processing/contracts/openapi-processing-monitor.yaml` je neparsovatelný na lifecycle description (řádek 66) a sdílí generický `ObservationItem` i pro lifecycle DTO.
- Host review `plans/checkpoints/task-e0275532-1050-49c2-b1e3-b787751549bf.host-review.md` potvrzuje chybějící typové allowlisty, lifecycle DTO a formální error odpovědi; staré RED/acceptance zůstávají historické.
- Test `be-document-processing/tests/test_monitor_openapi_observation_contract.py` existuje, ale assertion požadující generické `details` odporuje zdrojovým briefům a musí být odvozen z jejich konkrétního kontraktu.
- Závazné briefy: `plans/tasks/2026-10-19_monitor-mvp-03-document-events-get.md`, `...-07-run-events-get.md`, `...-09-attempts-get.md`, plus briefy 11/13/15/17/19/21/24 a event/reducer briefy 06/08/10/12/14/16/18/20/22/23 a proposal `proposal-20261019-150954-c8891f`.
- Relevantní learning `learnings/architecture/2026-10-20_attemptstarted-audit-contract-preserves-producer-identity.md`: attempts jsou pouze pozorované AttemptStarted; nevymýšlet run identity/attempt counter a test kontraktu nevydávat za live-worker důkaz.
- Scope je přesně jeden YAML a focused contract test; zachovat ostatní worktree změny, žádné další API/spec, router, deployment ani live provider/AWS operace.

## Approach

- Zachovat přesně osm schválených observation paths; rozlišit požadované operace od skutečně dodaných/deployed operací.
- Modelovat per-operation kolekce s přesnými `oneOf`/discriminated per-event DTO allowlisty a `additionalProperties: false`; FileReceived nesmí nést run scope, attempt/page/run fields pouze validní typy.
- Definovat vlastní bounded lifecycle run summary, run detail a document audit DTO s explicitní unknown/ambiguous/partial, evidence a publication oddělenou od terminal status.
- Všechny úspěšné i 400/403/404/503 odpovědi formálně popíší JSON schema a `Cache-Control: private, no-store`. Popsat chybějící trusted identity-to-case authorization interface; shared API key je pouze service authentication.
- Zachovat bounded window, limit 1–100, scoped opaque operation-bound continuation, `items`/`next_token`/`observed_at`, požadované `coverage: partial`, empty items s tokenem; žádné snapshot/latest/complete/totals, content/raw errors/S3/artifact paths ani synthetic business statuses.

## Implementation

1. Před RED ověřit z kořene repozitáře funkční interpreter i dependency/importy: `be-document-processing/.venv/bin/python -c 'import yaml, pytest'`.
2. Aktualizovat nejprve existující focused test: odstranit vadný požadavek generického `details`; doplnit konkrétní path/parameter/ref, event allowlist, lifecycle DTO, error/header a forbidden-field assertions podle briefs, ne podle nynějšího YAML.
3. Zachytit skutečný RED a následně GREEN stejným přesným focused argv a pouze přes načtený `skill:tdd` workflow; proof ukládat pod task ID `task-b96084af-3aa2-438d-a562-900bbdad7e95` do kořenového `plans/checkpoints/`. Nezaměňovat chybějící interpreter/dependency/conftest za RED; při permission denial nic neobcházet.
4. Opravit jediný YAML, rozdělit observation/event/lifecycle response schemas, zapsat explicitní status-code response objekty i pro errors a vyřešit všechny `$ref`-y.
5. Spustit focused test, parse+lokální-ref+schema validaci a relevantní package pytest; potom oba registrované gates `npm --prefix apps/backoffice test` a `npm --prefix apps/backoffice run build`. Případnou nesouvisející collection chybu popsat přesně, bez vyloučení testů nebo změkčení assertions.

## Testing

- Interpreter/dependency preflight: `be-document-processing/.venv/bin/python -c 'import yaml, pytest'` (z repo root).
- Focused RED i GREEN použijí shodně: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_openapi_observation_contract.py` (z repo root; suite prefix je `be-document-processing/tests/`).
- Ověřit YAML parse, OpenAPI 3.x, všechny lokální `$ref`, přesné osm paths, path/query scope a 1–100 limit; typové allowlisty a lifecycle shapes; error response statuses/headers; partial/empty continuation; vyloučení business listů/content paths.
- Package pytest: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/`.
- Registrované gates: `npm --prefix apps/backoffice test` a `npm --prefix apps/backoffice run build`.

## TDD

Použít `skill:tdd` v implementačním tasku; ten samý focused test command pro RED i GREEN a vlastní proof v `plans/checkpoints/task-b96084af-3aa2-438d-a562-900bbdad7e95.red-green-proof.md`.

**Test file:** `be-document-processing/tests/test_monitor_openapi_observation_contract.py`  
**Framework:** pytest + PyYAML, existující repo dependency.  
**Run command (repo root):** `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_openapi_observation_contract.py`

```python
from pathlib import Path
import yaml

CONTRACT = Path(__file__).parents[1] / "contracts" / "openapi-processing-monitor.yaml"

def test_openapi_parses_and_references_resolve():
    document = yaml.safe_load(CONTRACT.read_text())
    assert document["openapi"].startswith("3.")
    # RED: malformed YAML fails parse; after syntax repair, subsequent contract assertions expose gaps.
    assert document["components"]["schemas"]["ObservationCollection"]

def test_event_and_lifecycle_contracts_are_specific_and_errors_are_private():
    document = yaml.safe_load(CONTRACT.read_text())
    schemas = document["components"]["schemas"]
    assert "FileReceived" not in schemas["FileReceivedObservation"]["properties"]["run_id"].get("enum", [])
    assert {"400", "403", "404", "503"} <= set(document["paths"][next(iter(document["paths"]))]["get"]["responses"])
    assert "RunDetail" in schemas and "DocumentAudit" in schemas
```

Skeleton assertions must be refined during test-first work to inspect actual schema structure (including resolved `oneOf` branches) and verify FileReceived excludes `run_id`, event-specific field allowlists, lifecycle evidence/publication/terminal separation, and `private, no-store` on every response. Do not preserve the invalid `details` expectation.

| Test | RED | GREEN |
|---|---|---|
| Parse and local refs | Current YAML parse fails at line 66; after syntax repair any dangling `$ref` fails explicitly. | YAML parses and every local reference resolves. |
| Event/lifecycle schemas and errors | Generic event union, missing lifecycle DTOs, and informal error statuses fail assertions. | Exact DTO allowlists, lifecycle distinctions and explicit private/no-store 400/403/404/503 responses satisfy assertions. |

## Files

| Path | Change |
|---|---|
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | Repair YAML and define precise event, collection, lifecycle and error response schemas. |
| `be-document-processing/tests/test_monitor_openapi_observation_contract.py` | Replace generic-detail assertion with source-brief-derived focused contract checks. |
| `plans/checkpoints/task-b96084af-3aa2-438d-a562-900bbdad7e95.red-green-proof.md` | Own-task RED/GREEN evidence after approved skill workflow. |
| `learnings/` | Save relevant session learning after main implementation task as explicitly required. |

## Progress

- [x] Read host review, current YAML/test, representative source briefs, and relevant learning.
- [x] Establish exact canonical plan path using required `plan-path.py` command.
- [ ] Implement focused test-first RED/GREEN and YAML contract.
- [ ] Run parse/ref/schema, package pytest, and registered backoffice gates.
- [ ] Save learning via `save-learning` after implementation.
