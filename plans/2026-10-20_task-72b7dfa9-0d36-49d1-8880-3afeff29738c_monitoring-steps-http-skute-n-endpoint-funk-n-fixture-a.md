# Plan 2026-10-20: Monitoring steps HTTP — endpoint, fixture a runtime důkaz

## Progress
- [x] Ověřeny zdroje, předchozí checkpoint, fixture, závislosti a hranice autorizace.
- [x] Připraven focused RED skeleton, implementační pořadí a live důkazní brány.
- [ ] Realizace a live acceptance náleží implementační fázi tohoto tasku.

## Analysis
- Checkpoint původního tasku: chyběla fixture `intake`, RED bylo setup failure, route ani deploy nevznikly; staré proof zůstane nedotčeno.
- `be-intake/app/main.py`: pouze upload/list, `x-api-key` middleware a `require_case()` kontroluje existenci; `processing_monitor_routes.py` chybí. Nejde o caller→case authorization. `audit_queries.read_document()` poskytuje jediné bounded Query a document-scope cursor, nikoli operation/run/attempt scope.
- `be-intake/tests/test_processing_monitor_step_routes.py` je nefunkční sketch s nedostupnou `intake` fixture; další monitor testy mají stejný problém.
- Funkční fixture je lokálně v `be-intake/tests/test_monitor_file_received.py:15–53`; v focused testu ji lze explicitně importovat. Projektový `be-document-processing/.venv` má pytest/FastAPI/boto3, ale aktuálně nemá `python-multipart==0.0.20` požadovaný `be-intake/app/requirements.txt`; package import vyžaduje `PYTHONPATH=be-document-processing/src`. Opravit prostředí a ověřit collection před RED, bez system-python fallbacku.
- `be-intake/app/Dockerfile` instaluje interní wheel a kopíruje pouze `main.py` a `content_hashes.py`; nový route modul musí být součástí image. Nalezený build/import postup je v `plans/monitoring/file-received-build-contract.md`; živou revizi ani autorizaci tím nelze doložit.
- `be-document-processing/contracts/openapi-processing-monitor.yaml` již deklaruje steps, ale `StepObservation` neobsahuje `PageCompleted/PageFailed`; upravit pouze steps DTO/operation. `audit_page_observations.to_page_observations()` je pure page mapper, ne step mapper.
- Learnings: `learnings/security-issues/intake-case-scope-authorization-and-tdd-red.md`, `learnings/architecture/2026-10-20_bounded-monitoring-read-plan-semantics.md`, `learnings/test-failures/acceptance-repair-preserve-tdd-evidence.md`: před route ověřit trusted auth; cursor poslední vyhodnocené pozice; collection failure není RED. Dokumentace `plans/monitoring/mvp-reference-20261019.md`, původní plán a checkpoint potvrzují test target i zatím chybějící seam. Recall helper: local fallback (kolekce `wonderfulkb-learnings` chybí), další vrácené case-client poznatky jsou pro tento endpoint nepřímé.

## Approach
- Nejprve doložit skutečný společný monitor HTTP seam (`processing_monitor_routes.py` dnes chybí): rozhraní identity→case entitlement, document-in-case lookup, pravidla 403/404, no-store i na middleware/exception odpovědích, 503 při selhání zdroje, a připojení jediného `read_document(table, case_id, document_id, limit, next_token)`; získat vlastníka/implementaci chybějícího základu, bez permissive stubu či nového identity frameworku. Pokud zůstane nedostupný, přesně zdokumentovat missing interface a blokaci SOURCE/DEPLOYED/LIVE; nepublikovat route.
- Nad prokázaným základem přidat samostatný `processing_monitor_step_routes.py`: jeden bounded evaluated window Query (1–100), filtrovat explicitní `(run_id, attempt_no)` a typy `StepStarted/StepFinished/StepFailed/PageCompleted/PageFailed`. Steps allowlist: `event_id, sequence, occurred_at, type, stage, run_id, attempt_no`, případně doložené `page_number, duration_ms, error_code`; `page_transcription` page outcome zůstává jediným terminal eventem. Bez odvozování stavu, trvání nebo duplicit; `coverage=partial`, `observed_at`, prázdná stránka může mít token.
- Operation=`steps` cursor nad existujícím dokumentovým reader tokenem validovat proti case/document/run/attempt a vázat jej na **LastEvaluatedKey**, nikoli poslední nalezený step; odmítnout malformed/cross-operation/scope token 400 před čtením. Token není oprávnění. Zachovat možnost začít refresh od začátku a nečíst další okna pro zaplnění stránky.
- V jediném OpenAPI YAML opravit pouze steps operation/DTO na skutečně povolené typed eventy a partial/empty continuation. Nenahrazovat unrelated operations a nepřepisovat `audit_queries.py` ani pure page mapper.

## Implementation
1. Ověřit a označit ownera společného monitor HTTP/auth/document-scope/reader základu: chybí v `be-intake/app/main.py`, žádný `processing_monitor_routes.py`; shared key + `require_case` není authorization. Doložit skutečný interface, případně zaznamenat blocker a zastavit exposure/deploy.
2. Před produkční úpravou zpřístupnit hermetickou fixture focused souboru explicitním importem existující lokální `intake` fixture (bez plošné změny conftest), doplnit autorizovaný caller/document mock podle reálného seamu. Do projektového venv nainstalovat chybějící intake test dependency `python-multipart==0.0.20` dle requirements; ověřit importy/collection. Vytvořit nový task-ID RED→GREEN proof pomocí `skill:tdd` stejným argv; zachovat původní failedinfra/proof.
3. Teprve po genuine RED a doložení seamu implementovat vlastní router/allowlist/scope cursor; minimálně jej zapojit do existující facade/`main.py`. Při chybě nutného read zdroje 503; odpovědi 200/400/401/403/404/503 private,no-store. Neshodu ve window nevykládat jako neexistující run/attempt.
4. Upravit steps DTO v jediném YAML a focused tests; spustit intake monitor regresi, audit + OpenAPI testy a registrovaný `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` bez vyřazení již failing testů.
5. Podle existujícího Dockerfile sestavit z repo rootu linux/amd64 image s audit wheelem i novým route souborem; offline runtime-user importem ověřit `main.app`, route a instalovaný package. Zjistit skutečný `wonderfulkb-ingest` App Runner target/owner, region, image repository, aktivní revizi/digest, env/IAM a podporovaný in-place release postup; neodvozovat aktuální stav z historické URL/digest. Uchovat ověřený recovery artifact/config a source→wheel→image digest.
6. Při autorizovaném cíli a podporovaném postupu provést revision/concurrency-guarded test deploy se zachovanou konfigurací, bounded rollout/health čekáním a kontrolou běžící image/revize/času. Permission denial neobcházet; bez dostupného operátorského rozhraní připravit Jackieho konkrétní artifact digest, target, config diff, recovery a jediný zbývající operator krok v témže zadání. Při poruše použít rollback pouze proti ověřené stále vlastní revizi.
7. Přes přímo nasazené HTTP bezpečně ověřit změněný GET na existujícím oprávněném syntetickém case/document/run s doloženým eventem; prověřit schema, typ/attempt/run, partial, continuation kde existuje, private,no-store a auth/scope negativní dle skutečné politiky. Předem zapsat fixture identity a malý write/request budget; využít již doložené syntetické události, žádný replay reálného dokumentu, ruční audit insert jako worker evidence, další inference nebo nejednoznačný POST retry. Read503 jen hermeticky. Opravit zjištěné route/package chyby v tomto scope, znovu otestovat a guardovaně zopakovat bounded smoke.
8. Do `plans/monitoring/` uložit task-specific redacted provenance, deploy/readback, HTTP status/ID/schema assertions, fixture/budget, výsledek či přesný blocker a stavy SOURCE / INSTALLED / DEPLOYED / LIVE-FUNCTION-VERIFIED. Rozlišit deployed route od neověřené živé obsahové větve a hermetických testů; dokončit review/acceptance dle dostupného manifestu a nakonec použít `save-learning` k zápisu alespoň jednoho poznatku.

## Testing
- Focused FastAPI/fake matrix: start+finish a failed step, terminal-only bez startu, oddělené pokusy/runy a source_validation bez page_number; PageCompleted/PageFailed pouze jednou bez syntetického StepFinished/Failed; bezpečný allowlist bez document content.
- Jediný Query se správným `Limit` a evaluated cursor i pro `items=[]` s pokračováním; žádný Scan ani další Query; odmítnutí cross-case/document/run/attempt/operation a malformed tokenu; invalid/missing attempt, limit mimo 1–100.
- Chybějící autorizace/scope, 400/401/403/404/503 a `private, no-store` včetně chyb. Zpětná kompatibilita FileReceived, run-events a attempts při prokázaném společném základu; netvrdit že deklarovaný YAML = hotové route.
- `PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_step_routes.py` po opravě prostředí; poté relevantní `be-intake/tests/test_monitor_file_received.py`, ostatní monitoring GET testy a `be-document-processing/tests/test_monitor_openapi_observation_contract.py` plus backend audit test suite přes stejný venv. Registrovaná gate přesně `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; kontrola `git diff --check`.
- Runtime: image digest/revision/config readback + změněná route se skutečným autentizovaným scoped eventem a příslušnými negativními HTTP odpověďmi; `/healthz` nebo `200 empty` není dostačující.

## TDD
**File:** `be-intake/tests/test_processing_monitor_step_routes.py` (nahradit stávající 404-necitlivý sketch; explicitní existující fixture). **Run command, totožné argv RED/GREEN:** `PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_step_routes.py`. Nejprve nainstalovat `python-multipart==0.0.20` do venv a ověřit collection, jinak jde o failedinfra, ne genuine RED. Implementace TDD cyklu dle `skill:tdd`; proof `plans/checkpoints/task-72b7dfa9-0d36-49d1-8880-3afeff29738c.red-green-proof.md`.

```python
from fastapi.testclient import TestClient
from test_monitor_file_received import intake  # explicitní lokální pytest fixture


def test_steps_returns_partial_window(intake):
    main, *_ = intake
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/cases/case-test/processing/documents/doc-test/runs/run-test/steps",
            params={"attempt_no": 1, "limit": 1},
            headers={"x-api-key": "test-key"},
        )
    assert response.status_code == 200  # RED: route dnes neexistuje (404)
    assert response.json()["coverage"] == "partial"
    assert response.headers["cache-control"] == "private, no-store"
```

| Test | Genuine RED | GREEN |
|---|---|---|
| `test_steps_returns_partial_window` | Po funkční fixture validní request dostane 404, ne 200 | Autorizovaná route vrátí bounded partial JSON a no-store |
| Rozšířená focused matice před produkční úpravou | Chybí filtrování/allowlist/operation cursor/error seam | Výše uvedené assertions včetně empty continuation, single Query, 503 a scope |

Pokud stále chybí trusted authorization fixture/interface, nevydávat GREEN přes stávající shared-key mock; zaznamenat skutečný blocker a zachovat proof.

## Files
- `be-intake/tests/test_processing_monitor_step_routes.py` — explicitní fixture, focused matrix a genuine RED.
- `be-intake/app/processing_monitor_step_routes.py` — vlastní GET, allowlist a operation-bound cursor.
- `be-intake/app/processing_monitor_routes.py`, `be-intake/app/main.py` — pouze skutečný společný seam a minimální router wiring po doložení ownera/interface.
- `be-intake/app/Dockerfile` — přibalit nový modul do existujícího image; zachovat interní wheel instalaci.
- `be-document-processing/contracts/openapi-processing-monitor.yaml` — pouze steps operation/DTO.
- `plans/checkpoints/task-72b7dfa9-0d36-49d1-8880-3afeff29738c.red-green-proof.md`, `plans/monitoring/` — vlastní proof a runtime evidence bez secrets/obsahu.
