# Plan 2026-10-20: Monitoring OpenAPI — přesná povinná pole a status enumy eventových DTO

Zpřesnit pouze existující observation OpenAPI YAML a jeho focused contract test. Zachovat stávající osm cest, bounded lifecycle DTO, bezpečnostní/popisy a historické důkazy; bez runtime implementace nebo deploymentu.

## Analysis

- `plans/checkpoints/monitoring-parallel-20261020/openapi-review-0856.md` potvrzuje validní YAML a čtyři dosavadní focused testy, ale chybí required-field/status fidelity a validace reprezentativních payloadů.
- Aktuální event schémata jsou `additionalProperties: false`, ale řada briefem vyžadovaných run/attempt/stage/page scope polí zůstává nepovinná. `AttemptFinished` a `RunFinished` chybně používají `outcome` místo `attempt_status`/`run_status`.
- Source of truth: `plans/tasks/2026-10-20_monitor-mvp-22-retry-terminal-events.md` (terminální a retry), `...-20-publication-events.md` (ResultPublished), `...-12-page-outcome-events.md` (page/stage) a schválené briefy 06/08/10/12/14/16/18/20/22. Při konfliktu neodvozovat kontrakt z generického pole ani runtime změny.
- `learnings/test-failures/monitoring-openapi-semantic-validation.md`: parse/ref nestačí; použít offline `openapi_spec_validator.validate_spec`, rozřešit ref větve a testovat payload validitu i odmítnutí.
- `learnings/architecture/2026-10-20_monitoring-read-api-plan-scope.md`: shared API key není case authorization; unavailable trusted auth interface musí zůstat výslovně popsáno.
- Proveď review všech existujících event variant vůči jejich briefům včetně required scope, result/retry polí, safe allowlistů a enumů/types. Rozliš interní envelope od veřejného DTO a neexportuj automaticky interní pole.

## Approach

Uprav jen smlouvu a focused test. Zachovej přesně osm operation paths, one-window/partial/continuation pravidla, oddělené lifecycle/evidence/publication semantics, neznámou auth hranici a 400/403/404/503 s `private, no-store`. `FileReceived` zůstává bez run scope; `RunFinished.attempt_no` zůstává volitelné; terminal-only fragment neoslabuje povinná pole ostatních eventů. Nezměň event producer ani historii failed/inconclusive acceptance/TDD proof.

## Implementation

1. Nejprve rozšiř `test_monitor_openapi_observation_contract.py` o briefově odvozenou tabulku `event type → required/prohibited fields, types, enums`; pokryj RunQueued, AttemptStarted, step/page variants, ResultPublished, RetryEnqueued, AttemptFinished a RunFinished.
2. Přidej platné a neplatné příklady payloadů pro každé odlišné kontraktní pravidlo: chybějící required scope/status, chybný enum/type, zakázané extra pole, FileReceived s run_id a RunFinished bez attempt_no. Validuj přes dostupný offline JSON Schema/OpenAPI validátor.
3. Spusť genuine RED přes načtený `skill:tdd` povoleným `proof-capture.py` interface; použij vlastní task ID a z kořene repo stejnou focused argv pro RED i GREEN: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_openapi_observation_contract.py`.
4. Uprav YAML event schemas podle briefů: required lists, přesné enumy/status názvy a typy; odstraň nepodložený generický `outcome`. Udrž bezpečné allowlisty a public/internal boundary.
5. Získej GREEN stejnou argv a zachovej samostatnou proof cestu pod tímto task ID. Staré proofy ani verdict nepřepisuj.
6. Ověř focused test, celé `be-document-processing/tests/`, `npm --prefix apps/backoffice test` a `npm --prefix apps/backoffice run build`. Nezakrývej collection/environment chyby; odliš unrelated blocker od vlastního výsledku.

## Testing

- YAML parse, OpenAPI `validate_spec`, lokální `$ref` resolution a přesně osm operation paths.
- Pro každý event payload testuj validní případ i klíčová odmítnutí required/forbidden fields, typů a enums; potvrď `AttemptFinished(run_id, attempt_no, attempt_status)` a `RunFinished(run_id, run_status)` s enumem `completed|partial|failed`.
- Ověř zachování collection/response/error/cache/auth/lifecycle pravidel a žádný content, raw error, S3 key ani artifact path.
- Spusť focused pytest, package pytest i registrované backoffice test/build příkazy přesně dle zadání.

## TDD

Implementující agent použije `skill:tdd` a její povolené rozhraní; nevytváří ručně proof. Focused test musí selhat kvůli chybějící sémantice, nikoli dependency/import/collection problému. RED a GREEN použijí totožnou argv a záznam bude `plans/checkpoints/task-eb1279da-fb6b-42ed-9551-8fa3fb753515.red-green-proof.md`.

Test skeleton pro první RED assertion (doplnit do existujícího testu použitím jeho YAML loader/helper):

```python
def test_terminal_event_contracts_require_exact_status_and_scope():
    document = yaml.safe_load(CONTRACT.read_text())
    schemas = document["components"]["schemas"]
    attempt = schemas["AttemptFinished"]
    run = schemas["RunFinished"]
    assert {"run_id", "attempt_no", "attempt_status"} <= set(attempt["required"])
    assert attempt["properties"]["attempt_status"]["enum"] == ["completed", "partial", "failed"]
    assert {"run_id", "run_status"} <= set(run["required"])
    assert run["properties"]["run_status"]["enum"] == ["completed", "partial", "failed"]
    assert "attempt_no" not in run["required"]
```

| Assertion | RED | GREEN |
|---|---|---|
| AttemptFinished exact required fields/status enum | Current schema lacks required status name and enum | YAML and valid/invalid payload checks match brief |
| RunFinished required run/status; optional attempt | Current schema uses unconstrained `outcome` | Required run/status enum; attempt remains optional |

Focused command for both proof phases: `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests/test_monitor_openapi_observation_contract.py`.

## Files

| Path | Planned change |
|---|---|
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | Correct per-event required scope, exact status/result/retry enums/types and allowlists; preserve existing paths and shared response/lifecycle guarantees. |
| `be-document-processing/tests/test_monitor_openapi_observation_contract.py` | Add brief-derived schema/payload semantic checks and offline OpenAPI validation. |
| `plans/checkpoints/task-eb1279da-fb6b-42ed-9551-8fa3fb753515.red-green-proof.md` | Generated only by approved TDD proof interface during implementation. |

## Progress

- [x] Read independent contract review and inspect current owned YAML/test.
- [x] Identify authoritative event briefs and applicable validation learning.
- [x] Define bounded implementation and verification sequence; no implementation performed.

---
*Created: 2026-10-20*
