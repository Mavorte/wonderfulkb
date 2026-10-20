# Plan 2026-10-20: Monitoring steps HTTP: skutečný bounded endpoint se sdílenou case autorizací a test deploymentem

## Analysis
- Při planning retry zachovat tento soubor a opravit příčinu `invalid_header`: první řádek musí začínat `# Plan YYYY-MM-DD:`; před předáním validovat celý artefakt, ne pouze povolené sekce.
- Reuse `processing_monitor_routes.authorized_document/read_authorized_window`, middleware `main.guard` a `AuditStore.read_document`; nové steps requests již spadají do SERVICE auth větve.
- Zachovat historický proof `plans/checkpoints/task-72b7dfa9-0d36-49d1-8880-3afeff29738c.red-green-proof.md`; existující steps test má explicitní funkční intake fixture, ale vyžaduje přechod na doložený SERVICE grant místo samotného x-api-key.
- Před přidáním mapperu znovu prověřit aktuální diff: v prohlédnutém audit package existuje pouze page mapper a lifecycle reducer, nikoli pure step mapper; `audit_queries.py` již dekóduje všechny tři Step typy.
- Vyřešit pouze steps DTO rozpor: YAML znovupoužívá obecné event schemas, má optional sequence a vyžaduje duration na StepFinished; skutečný event má duration optional. Ostatní operace zachovat.
- Použít pravidla z `learnings/test-failures/intake-monitoring-red-multipart-explicit-fixture.md` a `learnings/architecture/2026-10-20_lifecycle-http-plan-auth-reader-image-seams.md`: projektový venv, explicitní fixture, COPY routeru a import pod UID10001.

## Approach
- Řídit implementaci proposalem `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md`, sekce `read-api`, `delivery`, `slice-source-validation`, včetně schválení SERVICE grants 20.10.2026 10:01.
- Ověřit současný diff před každou úpravou; zachovat existující cizí změny, historické tasky, failed/inconclusive evidence i původní RED. Tento plán propojit s implementačním checkpointem, neupravovat task lifecycle/instrukce.
- Reuse existující pure step mapper, pokud jej aktualizovaný checkout doloží. Aktuálně chybí v `be-document-processing/src/document_processing/audit/` i intake; pokud se to potvrdí, doplnit pouze malou pure allowlist funkci v doménovém `processing_monitor_step_routes.py`, žádný paralelní reader nebo nový společný modul.
- Načtení omezit na jediný existující evaluated document Query; filtrovat až jeho výsledek. Pořadí zachovat technické `EVENT#event_id`, neslibovat chronologii `occurred_at,event_id` z obecného proposalu; tento konkrétní existující rozpor doložit v task evidence bez přestavby store.
- Použít `skill:tdd` pro genuine proof; po implementaci `validate-implementation`, `code-review` a `write-review-report`, acceptance dle skutečného caller manifestu; `save-learning` jako poslední krok. Při AWS realizaci použít `aws-containers`, při nutném přihlášení `signing-in-to-aws`; nový Wonderful deployment není součástí intake dodávky.
- Převzít learnings o explicitní fixture/venv, bounded Query a source vs deployed evidence; recall helper použil `backend=local`, `collection=wonderfulkb-learnings`, diagnostic `Collection not found`. Pro planning retry použít také `learnings/tooling/2026-10-20_planning-retry-canonical-header-validation.md`; canonical validátor kontroluje prefix `# Plan` nezávisle na názvech sekcí. Při implementaci ověřit existující read/build dokumentaci.

## Implementation
1. Ověřit git diff a aktuální auth/read/mapper rozhraní proti tomuto plánu; ověřit venv závislosti `pytest`, `fastapi`, `httpx`, `multipart`, `boto3`, `moto`, `yaml`, `jsonschema`, `openapi_spec_validator` a cwd kořen wonderfulkb. Případné chybějící závislosti instalovat z existujících pinů, ne systémovým Pythonem. Neprovozovat cloud operace během plánování.
2. Jako první behaviorální změnu upravit vlastní `be-intake/tests/test_processing_monitor_step_routes.py`: reuse explicitní `intake` a existující `monitor` fixture se SERVICE binding/grant a trusted document metadata. Starý happy test převést na tuto schválenou auth precondition, zachovat jeho assertions i původní proof. Přidat matici níže, capture genuine RED před production změnou.
3. Přidat `be-intake/app/processing_monitor_step_routes.py` s GET `/runs/{run_id}/steps`, `attempt_no=Query(..., ge=1)`, `limit=Query(50, ge=1, le=100)` a omezeným neprázdným `next_token`. Validovat run identifikátor stejným `validate_identifier`; chybějící/malformed attempt, limit, scope a token vrací 400 přes stávající error handling.
4. Reuse `authorized_document` po middleware SERVICE auth; retained historie vyžaduje tentýž aktuální case grant a server-attested document tuple. Missing/forged/revoked/mismatched principal odmítnout před document/audit reads; auth-source a membership failure vrací bezpečné 503, skutečně neexistující dokument 404. Žádný nový autorizační provider ani fallback na x-api-key/case existence/header.
5. Vlastní cursor adapter zabalí reader token do přesně validovaného versioned envelope `{operation: steps, case_id, document_id, run_id, attempt_no, reader}`; včetně vnitřního document tokenu ověřit před Query, obal i payload size omezit. Nepřebírat lifecycle wrapper bez attempt pole. Předat rozbalený cursor do `read_authorized_window` právě jednou; vrátit obal `page.next_token` od LastEvaluatedKey i při prázdných items.
6. Pure mapper/projekce explicitně přijme pouze source_validation `StepStarted/StepFinished/StepFailed` pro přesné run/attempt. Vydat povinné `event_id/sequence/occurred_at/type/stage/run_id/attempt_no`; `duration_ms` jen skutečně uložené na terminal eventech, `error_code` pouze na failed dle interního allowlistu. Decimal serializovat přes existující FastAPI encoder. Source_validation nikdy nevydá page_number, case/document IDs, schema_version, raw errors ani obsah.
7. Zachovat každý uložený event jednou, terminal-only i start-only fragmenty; nic nepárovat, nedopočítávat duration/status/totals a nevyžadovat RunQueued/AttemptStarted. Omezit mapper tabulkou event type + stage → allowed fields; PageCompleted/PageFailed ponechat budoucímu page slice jako jediné page terminály, bez nynější aktivace page/extraction/signature/publish větví nebo producer změn.
8. Vrátit přesně `items/next_token/observed_at/coverage=partial` a private,no-store. Read/decoder/projection failure musí zůstat bezpečné 503, nikdy empty200. Reuse main middleware a validation handler i pro errors; main změnit pouze import/include_router, facade jen pokud je doložen nutný drobný seam.
9. V jediném `be-document-processing/contracts/openapi-processing-monitor.yaml` upravit pouze steps operation/StepObservation a její vlastní DTO branches: required sequence, přesný source_validation allowlist, optional doložená duration i pro failed, skutečné bezpečné error codes. Nezměnit obecné Step event schemas používané ostatními operacemi. Pro steps doplnit SERVICE bearer security scheme/reference, protože globální ApiKeyAuth a text o nedostupné autorizaci již nepopisují tuto route; globální security a ostatní operace zachovat, rozpor zdokumentovat. Přidat validaci skutečné nonempty HTTP response proti tomuto DTO v existujícím YAML.
10. Přidat explicitní `COPY --chmod=644` nového HTTP modulu do `be-intake/app/Dockerfile`; reuse stávající wheel build/non-editable instalaci. Získat GREEN identickou argv, spustit úplné relevantní gates, package/image import a router assertion pod UID10001 bez source mount/PYTHONPATH.
11. V témže implementačním tasku ověřit AWS účet/region a existující `wonderfulkb-ingest` App Runner TEST ARN, owner Jackie, běžící revision/digest, env/secrets/IAM a ECR repository. `be-intake/template.yaml` definuje IAM/secret, nikoli App Runner service; deploy postup zjistit od existujícího ownera/config, nevymýšlet nový framework. Uchovat ověřenou dostupnou recovery image a bezpečný config snapshot mimo repo; evidence bez secret hodnot.
12. Build `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:steps-task-252c7fcd .`; zapsat source blob/wheel/image hashes, ověřit instalovaný audit package ze site-packages a route v final image. Push jen do ověřeného existujícího ECR, immutable task tag; zaznamenat registry digest a porovnat source manifest se skutečně nasazovaným artefaktem.
13. Před update znovu porovnat revision/config/digest a ověřit, že neběží cizí rollout; serializovat přes existující owner deployment guard. Při driftu zastavit a znovu koordinovat, nikoli přepsat cizí změnu. Provedení pouze guarded in-place změny image, zachovat env/IAM/secrets. Poll nejvýše 15 minut po 15 s, vyžadovat completed operation, RUNNING službu a readback správné image/revision/digest. Při vadném rollout použít ověřenou recovery pouze pokud guard stále prokazuje vlastnictví revize.
14. Před live čtením zapsat konkrétní syntetické case/document/run/attempt ID a trusted membership/provenance do vlastní evidence; reuse bezpečné existující fixture. Grant výhradně vyjmenovanému case, bez wildcard. Preferovat existující události; pokud bezpečný fixture nemá source_validation event, nejvýše tři označené reader-only Step eventy přes existující idempotentní store, s deterministic task IDs a přesným readbackem. Neoznačovat je worker producer proof; nevyvolávat upload/worker/inference.
15. Před cloud writes zkontrolovat existující ledger/owner budget a odečíst dosavadní spotřebu; tento plán žádný vyčerpaný budget neresetuje. Použít přísnější z existujícího omezení a stropu: 2 candidate rollouty (první + jedna doložená oprava), 1 recovery rollout, 12 live HTTP GET, 0 POST/upload/business writes, 3 audit event insert attempts. Výchozí auth-policy writes 0; pokud je nutný explicitní synthetic grant, nejvýše 1 guarded policy update a 1 recovery, s očekávaným Secret VersionId a zachováním ostatních grants. Počet kontrolních AWS reads a každý write/request vykázat; ambiguous write nereplayovat, nejprve zjistit skutečný stav. Vyčerpání budgetu nebo chybějící bezpečný fixture jsou blocker, ne green.
16. Live přímo na test URL assertovat nonempty nový DTO (přesné event IDs/types/stage/run/attempt, sequence, observed_at, coverage, safe duration/error, absence page/content), no-store, dvě bounded stránky včetně empty continuation tam, kde bezpečný fixture dovolí, wrong-attempt filtr, cross-scope/operation token400 a unauthenticated403. Případný reader-only fixture rozvrhnout před writes tak, aby prokázal continuation; read failure503 ověřovat hermeticky bez cloud fault injection.
17. Pokud runtime nemá deploy capability nebo nastane skutečné permission denial, předat Jackiemu přesný digest/target/config diff/recovery/guard/operator krok v rámci tohoto tasku; po provedení doplnit vlastní readback/live assertions. V `plans/monitoring/task-252c7fcd-6de4-4406-813b-e7771d61da74-runtime-evidence.md` odděleně doložit SOURCE / INSTALLED / DEPLOYED / LIVE-FUNCTION-VERIFIED, command outcomes, request/write ledger a konkrétní blocker. Health/empty200/runbook nenahrazují funkční důkaz.
18. Provést review/validation a uložit review report přes `write-review-report`, vyhodnotit skutečné acceptance gates, poté `save-learning`. Neuzavírat implementační dodávku jako úspěšnou bez deployed+live výsledku; tento dokument nyní dokončuje pouze plánování.

## TDD
- Implementace TDD cyklu dle `skill:tdd`; nový proof výhradně `plans/checkpoints/task-252c7fcd-6de4-4406-813b-e7771d61da74.red-green-proof.md`, historické proof neměnit ani kopírovat jako nový výsledek.
- Cwd pro oba capture je `/Users/michal/Projects/wonderfulkb`. Nejdřív ověřit dependency/import a collection bez spouštění behavior testu; dependency/import/fixture failure není RED.
- Do existujícího `be-intake/tests/test_processing_monitor_step_routes.py` přidat tento spustitelný skeleton; `monitor` fixture je explicitně definovaná v `test_processing_monitor_routes.py`, nikoli v neexistujícím conftest. Stávající test současně přepnout na schválený autorizovaný fixture.

```python
from fastapi.testclient import TestClient
from test_monitor_file_received import intake  # explicit fixture dependency
from test_processing_monitor_routes import monitor, HEADERS
from document_processing.audit.audit_events import StepFinished


def test_steps_returns_real_terminal_only_observation(monitor):
    main, _, _, _, _, table = monitor
    event = StepFinished(
        schema_version=1, event_id="steps-terminal", sequence=7,
        case_id="case-test", document_id="doc-test", type="StepFinished",
        occurred_at="2026-10-20T10:00:00Z", run_id="run-test",
        attempt_no=1, stage="source_validation", duration_ms=12.5,
    )
    table.query.return_value = {"Items": [event.to_item()]}
    with TestClient(main.app) as client:
        response = client.get(
            "/v1/cases/case-test/processing/documents/doc-test/runs/run-test/steps",
            params={"attempt_no": 1, "limit": 1}, headers=HEADERS,
        )
    assert response.status_code == 200  # RED: authorized route is missing
    body = response.json()
    assert body["items"] == [{
        "event_id": "steps-terminal", "sequence": 7,
        "occurred_at": "2026-10-20T10:00:00Z", "type": "StepFinished",
        "stage": "source_validation", "run_id": "run-test", "attempt_no": 1,
        "duration_ms": 12.5,
    }]
    assert body["coverage"] == "partial" and body["next_token"] is None
    assert body["observed_at"]
    assert response.headers["cache-control"] == "private, no-store"
    table.query.assert_called_once()
    assert table.query.call_args.kwargs["Limit"] == 1
    table.scan.assert_not_called()
```

```bash
TASK_ID=task-252c7fcd-6de4-4406-813b-e7771d61da74 python3 "$HOME/.config/opencode/skills/tdd/scripts/proof-capture.py" red -- env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_step_routes.py
# Po accepted_red implementovat route; GREEN používá identickou child argv.
TASK_ID=task-252c7fcd-6de4-4406-813b-e7771d61da74 python3 "$HOME/.config/opencode/skills/tdd/scripts/proof-capture.py" green -- env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_step_routes.py
```

| Focused behavior | RED před route | GREEN |
|---|---|---|
| `test_steps_returns_real_terminal_only_observation` | 404 místo 200 při platném SERVICE grantu | Přesný nonempty DTO, 1 Query |
| Start+finish+failed, dva runy/dva pokusy | Chybějící observations | Přesný filtr, terminal-only/start-only zachován |
| Dvě stránky a empty evaluated continuation | Chybějící route/token | LastEvaluatedKey bez doplňujícího Query |
| Invalid scope/token a read failure | Chybějící handler | 400/503 a no-store; denial bez Query |

- Před production změnou doplnit celou focused matici níže a zachovat stejnou argv; accepted_red musí obsahovat behaviorální assertion, accepted_green child exit0. Po obou capture přečíst canonical proof, žádné ruční vytváření proof ani nové spuštění jen pro zachycení výstupu.

## Testing
- V actual FastAPI+middleware+AuditStore testech pokrýt start/finish/failed, source_validation bez page_number, optional duration (i absent), safe error allowlist, terminal-only bez startu a start-only bez syntetického výsledku; přidat Decimal roundtrip a vyloučení cizích payloadů/stages.
- Ve dvou runech/dvou pokusech ověřit filtr bez RunQueued/AttemptStarted; neexistující shoda v bounded okně vrací partial200. Pro 2 HTTP stránky assertovat přesně 2 Query, Limit a ExclusiveStartKey posledního evaluated eventu, včetně okna složeného pouze z neshod; na request právě 1 Query a 0 Scan.
- Tokeny cross-case/document/run/attempt/operation a malformed/oversize envelope i inner cursor odmítnout400 před Query, při cross-case nejprve zajistit validní explicitní test grant, aby test skutečně měřil token a ne auth403. Opačný směr steps→document/events musí také selhat400.
- Missing/zero/negative/noninteger attempt, limit0/101/noninteger, invalid run a prázdný token →400; missing/forged/disabled/revoked grant i client claims →403 bez document/audit read. Auth-source failure →503 bez Query, membership error→503, missing document→404; retained tuple funguje jen s aktuálním grantem. Všechny success/error odpovědi no-store.
- Audit read/decoder failure →503 bez úniku details; žádné asserts zmírněné kvůli unrelated failure. Actual response validovat proti jedinému YAML steps DTO a zachovat ostatní contract assertions.
- Spustit z kořene `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests` jako plnou intake/audit/Python regresi, včetně FileReceived, run-events, attempts, lifecycle a OpenAPI testů. Neexistující nebo aktuálně rozbité sousední routes/fixtures evidovat jednotlivě jako selhání, ne ignore/xfail nebo zelený celek; jejich implementaci neabsorbovat.
- Povinný registrovaný gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` (timeout 300 s); zachovat oba příkazy i jejich skutečné výsledky. Dále `git diff --check` pro vlastní změny a image import/router check pod runtime userem.
- Dokončit live assertions a ledger dle kroků11–17; nepovažovat lokální TestClient, package import ani healthy rollout za LIVE-FUNCTION-VERIFIED.

## Files
| Soubor | Konkrétní změna |
|---|---|
| `be-intake/app/processing_monitor_step_routes.py` | Nový doménový handler, operation+attempt cursor a chybějící pure step projekce pouze pokud není k reuse |
| `be-intake/tests/test_processing_monitor_step_routes.py` | Reuse hotové intake/monitor fixture, genuine RED→GREEN a úplná focused HTTP matice |
| `be-intake/app/main.py` | Pouze import a include_router |
| `be-intake/app/Dockerfile` | COPY nového route modulu, zachovat wheel/runtime user |
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | Pouze vlastní steps operation/observation DTO/security reference, zachovat ostatní operace |
| `be-document-processing/tests/test_monitor_openapi_observation_contract.py` | Úzké nové assertions steps DTO/response bez oslabování stávajících |
| `plans/checkpoints/task-252c7fcd-6de4-4406-813b-e7771d61da74.red-green-proof.md` | Pouze automaticky generovaný nový task proof při implementaci |
| `plans/checkpoints/task-252c7fcd-6de4-4406-813b-e7771d61da74.checkpoint.md` | Implementační evidence a odkaz na tento canonical plán |
| `plans/monitoring/task-252c7fcd-6de4-4406-813b-e7771d61da74-runtime-evidence.md` | Source→wheel→image→rollout→live assertions a bounded write/request ledger |

- `processing_monitor_authorization.py`, `processing_monitor_routes.py`, audit event/store/query package a fixture foundation reuse; úpravu společné facade připustit jen při doloženém minimálním technickém seam, ne refaktor.

## Progress
- [x] Získat canonical cestu pro task-252c7fcd-6de4-4406-813b-e7771d61da74.
- [x] Ověřit současný source/tests, společnou autorizaci, audit kontrakty, historický RED a package/deploy hranice.
- [x] Připravit konkrétní TDD skeleton, implementační kroky, gates a bounded test deployment/live proof.
- [ ] Při implementaci splnit kroky1–18; tento plán sám nedokládá spuštění testů, instalaci ani nasazení.
