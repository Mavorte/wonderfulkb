# Plan 2026-10-20: Monitoring MVP: použití cache ve stávajícím stránkovém API

## Analysis
- Zachovat již přítomné `PAGE_TYPES`, `to_page_observations`, reader registraci PageCacheReused, YAML DTO a `test_processing_monitor_cache_reused.py`; nejprve ověřit jejich aktuální provenance a skutečné mezery, nekopírovat implementaci.
- Navázat na kontrakty `plans/tasks/2026-10-20_monitor-mvp-14-cache-reused-event.md` a `2026-10-20_monitor-mvp-13-attempt-pages-get.md`; cached_* popisuje uložený výsledek, nikoli novou práci.
- Použít learnings `page-cache-reused-reader-registration.md`, `2026-10-20_page-cache-reused-artifact-roundtrip.md` a `2026-10-19_case-client-source-contract-vs-deployed-state.md`: registrace readeru, list/tuple roundtrip a source/live důkaz jsou oddělené kontroly. Recall: backend=local, collection=wonderfulkb-learnings, diagnostic=Collection not found.
- Před runtime kroky znovu ověřit handoff `plans/handoffs/aws-runtime-readiness-20261020.md`: historicky chyběl execution/audit worker env a Docker kapacita; neoznačovat historický problém za aktuální bez readbacku.
- Navázat na vlastní `plans/monitoring/task-0e56cd5e-0911-4acb-bcf6-4df33a97a46c-cache-read-evidence.md`: historicky SOURCE/INSTALLED, nikoli DEPLOYED/LIVE; zachovat původní neúspěchy i recovery JSON. Znovu ověřit run-events seam, který tehdy chyběl a nyní má testy.
- Zachovat ledger: max. 12 HTTP GET, historická spotřeba 0; metadata GetItem 2 a chybně klíčované Query 2 již provedeny. Před pokračováním sloučit případné novější záznamy, limit neresetovat. Audit klíč tvoří `document_key(case_id, document_id)` (JSON pole), nikoli `CASE#...`.

## Approach
- Zachovat jediný `read_authorized_window` → `AuditStore.read_document` → jeden bounded Query. V page route filtrovat run/attempt/type/stage/page před čistým mapperem; nezměnit poslední vyhodnocenou pozici ani token scope case/document/run/operation=pages/attempt_no.
- Vrátit pouze společnou observation obálku a známé cached_status/method/model/artifact_ids; unknown vynechat. Zachovat completed i failed reuse fragment bez startu a bez původního cache eventu. Stejný event_id/type/time/sequence zpřístupnit přes document/run events.
- Zachovat samostatné observations stejné stránky; reuse nevytváří PageCompleted/StepFinished, počty dokončení, total/procenta ani novou inference. Steps musí reuse vyloučit, i když sdílí page mapper.
- Zachovat current trusted case grant, exact membership, 403/404, read/DTO503 a private,no-store včetně chyb. Nepřidávat Scan, fill loop, latest stav, index, cache lookup, resolver, endpoint ani producer hook.

## Implementation
1. Před změnou ověřit aktuální diff/hash vlastních souborů a sousedních owner změn. Přečíst vlastní evidence, recovery a canonical TDD proof; původní task soubor ani cizí source neupravovat. Použít `skill:tdd` a `skill:task-evidence` pro navázání skutečného historického cyklu, nikoli jeho přepis.
2. Spustit focused baseline dle TDD; případnou novou behaviorální mezeru nejprve zachytit selhávajícím testem, potom úzce opravit page allowlist/DTO nebo delegation seam. Již přítomnou implementaci ponechat; `audit_queries.py` nepřestavovat. Chybějící vlastněný run-events interface doložit jako konkrétní blocker bez výroby další route.
3. Ověřit jediný YAML pro pages a PageCacheReusedObservation/DocumentEvent/RunEvent: cached_* význam, coverage=partial, empty continuation, identita a zakázané content/internal fields; změnit jen zjištěný rozdíl, zachovat ostatní operace. Spustit regrese a registrovaný gate níže.
4. Nainstalovat `be-document-processing/.venv/bin/python -m pip install --no-deps -e ./be-document-processing`; build z rootu: `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:task-0e56cd5e .`. Dockerfile již vytváří a noneditable instaluje wheel bez worker dependencies; neměnit tento postup. Zaznamenat source manifest, wheel hash, image index/amd64 manifest/config digest.
5. Ve finálním image ověřit UID10001, import audit package ze site-packages, zapojený page router a přímo pages completed/failed reuse, unknown model, event parity a steps exclusion. Reuse `be-intake/tests/image_processing_monitor_smoke.py`; doplnit pouze chybějící cache-pages assertions. Spouštět bez sítě a source mountů, pouze hermetické provider fakes; import nebo document-events-only cache smoke nestačí.
6. Před cloud operací načíst `skill:signing-in-to-aws` a jeho `references/wonderfulkb-test-access.md`; AWS přes oficiální MCP po signed STS účtu 609394381050/regionu eu-central-1. Lokální podporované nástroje musí explicitně používat profil ai-hackathon a region eu-central-1; žádný AWS CLI přes Bash. Při expiraci požádat hosta o existující SSO renewal, skutečný denial neobcházet. Pro image/ECR/App Runner použít `skill:aws-containers`; případný Python SDK helper vyžaduje `skill:aws-sdk-python-usage`.
7. Zjistit aktuální owner, lock `plans/monitoring/.intake-deployment.lock`, ledger, service/operations a ECR provenance. Target je `arn:aws:apprunner:eu-central-1:609394381050:service/wonderfulkb-ingest/c9ef96fae3da4192abd7e8280d43ae6b`; host vždy z DescribeService. Ověřit reálné install/push/deploy prerequisites a kompatibilitu audit writer/reader/table klíčů podle runtime handoffu; žádný backfill/reset ani schema migrace v tomto slice.
8. Uchovat a importem/digestem ověřit současný recovery image a bezpečnou config zálohu; historický host-frozen digest z evidence nepovažovat automaticky za současný. Zachovat env/secret references/IAM a auto-deploy nastavení. Pod existujícím owner lockem znovu porovnat image identifier/digest, config fingerprint a poslední operations bez in-flight operace; samotné UpdatedAt není revision guard. Při driftu zastavit mutation.
9. Existujícím native owner postupem pushnout ověřený immutable artifact a provést in-place App Runner update pouze image reference; nevymýšlet deploy skript/framework. Pollovat operation nejvýše 20 minut (30s interval) do úspěchu a RUNNING/health; poté znovu resolve ECR digest a service config/operation times. Timeout není success. Pokud interface/oprávnění chybí, připravit Jackiemu v témže tasku digest, target, úzký config diff, recovery a přesný zbývající owner command; po jeho kroku pokračovat ověřením.
10. Provést níže popsané bounded live HTTP; scoped source/package/router chybu opravit, znovu ověřit a guardovaně nasadit v témže tasku pouze v rámci zbývajícího ledgeru. Při outage použít ověřený recovery postup s kontrolou aktuální vlastní revize, nepřepsat cizí rollout.
11. Appendovat vlastní evidence o SOURCE / INSTALLED / DEPLOYED / LIVE-FUNCTION-VERIFIED, digest/revision/operation time, installation/deploy outcome, fixture IDs, request count a safe assertions. Chybějící nonempty reuse fixture ponechat jako přesný live-content blocker. Použít `skill:validate-implementation`; při review také `skill:write-review-report`, acceptance jen dle skutečně dodaného manifestu (`skill:acceptance`). Nakonec `skill:save-learning`.

## Files
| Cesta | Zamýšlená úprava / kontrola |
|---|---|
| `be-intake/app/processing_monitor_page_routes.py` | Vlastněný allowlist/filter/DTO a pages cursor; jen prokázané mezery. |
| `be-document-processing/src/document_processing/audit/audit_page_observations.py` | Reuse hotového čistého mapperu, bez kopie. |
| `be-document-processing/src/document_processing/audit/audit_queries.py` | Ověřit existující PageCacheReused registraci a jeden Query; bez refaktoru readeru. |
| `be-intake/app/processing_monitor_routes.py`, `processing_monitor_step_routes.py`, `main.py` | Ověřit public event parity, explicitní executed-step allowlist a zapojení routeru; jen nutný malý seam diff. |
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | Jediný kontrakt; vlastní pages/reuse DTO a operation, ostatní zachovat. |
| `be-intake/tests/test_processing_monitor_cache_reused.py` | Reuse existujících 12 focused případů, případně doplnit skutečný gap. |
| `be-intake/tests/image_processing_monitor_smoke.py`, `be-intake/app/Dockerfile` | Ověřit instalovaný artifact a přímo cache-pages větev; Dockerfile měnit jen při doložené packaging chybě. |
| `plans/monitoring/task-0e56cd5e-0911-4acb-bcf6-4df33a97a46c-cache-read-evidence.md` | Appendovat nová data a ledger, zachovat historii a recovery vazby. |

## TDD
- Implementace TDD cyklu dle skill:tdd. Zachovat existující pravý proof `plans/checkpoints/task-0e56cd5e-0911-4acb-bcf6-4df33a97a46c.red-green-proof.md`: RED 2026-10-20 09:49Z = 5 failed/7 passed, GREEN 09:50Z = 12 passed; dnešní běh tím není nahrazen.
- Test file: `be-intake/tests/test_processing_monitor_cache_reused.py`; pytest/FastAPI TestClient, skutečné module-local fixtures. Spouštět z rootu: `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_cache_reused.py`.
- Použít existující test `test_reuse_fragment_survives_pages_and_document_events` (nekopírovat); minimální executable skeleton jeho behaviorálního jádra s reálnými importy:

```python
import pytest
from test_monitor_file_received import intake  # noqa: F401
from test_processing_monitor_routes import monitor, event
from test_processing_monitor_page_routes import get

@pytest.mark.parametrize("status", ["completed", "failed"])
def test_reuse_fragment_survives_pages(monitor, status):
    main, _, _, _, _, table = monitor
    table.query.return_value = {"Items": [event(
        "reuse-observed", type="PageCacheReused", sequence=7,
        run_id="run-test", attempt_no=1, stage="page_transcription",
        page_number=1, cached_status=status)]}
    response = get(main, limit=1)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1  # Skutečné historické RED: 0 != 1.
    assert items[0]["type"] == "PageCacheReused"
    assert items[0]["cached_status"] == status
    assert "model" not in items[0] and "cached_model" not in items[0]
    table.query.assert_called_once()
    table.scan.assert_not_called()
```

| Existing test / skeleton branch | Doložené RED před změnou | GREEN požadavek |
|---|---|---|
| reuse fragment, completed i failed | `len(items) == 1` dostalo 0 | Zachovaný cached_status, unknown model vynechán, stejné ID v events |
| reuse a nová práce | Chyběla reuse-observed/reuse-2 identita | Dvě stránky, izolace run/attempt, jeden skutečný PageCompleted |
| empty evaluated continuation | Druhé okno nemělo reuse item | Jeden Query/request, původní ExclusiveStartKey a bound token |

- Skeleton už na hotovém source může být GREEN: neodstraňovat fungující allowlist kvůli novému RED, nepřepisovat proof. Pro každou další opravu nejprve nový skutečně failing behaviorální assertion a helper-captured RED → minimální diff → GREEN se stejným argv; pokud nová chyba není, zachovat historický cyklus a zaznamenat aktuální regression GREEN.

## Testing
- Spustit focused cache test výše a `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests`; pokrýt cached completed/failed, unknown model/method/reference, dvě stránky/runy/attempts, PageCompleted+reuse bez double completion, fragment bez startu, document/run identity a steps exclusion.
- Zachovat testy bounded Query/Limit/no Scan, empty items+next_token, cross-operation/attempt/run token400, auth403, document scope404, read/decode503 a private,no-store pro každou větev; assertions nulového cache/model/S3/write I/O. Read failure pouze hermeticky.
- Spustit dřívější širší regresi: `PYTHONPATH=be-validator-agent/trigger:be-validator-agent/pipeline be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests be-validator-agent/trigger/tests be-validator-agent/pipeline/tests`; nezakrýt předchozí run-events failure ani cizí nový failing test.
- Zachovat přesný registrovaný gate (timeout 300 s): `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; dále `git diff --check`. Testy a build v této plánovací fázi nespouštět.
- Před live číst za běhu pouze in-memory secret names z access runbooku: ingest-api-key, monitoring-synthetic-bearer-20261020 a monitoring-synthetic-20261020 policy. Ověřit hash, active credential, přesný grant a current membership pro SYN-A01 / 34fcd896-107a-583f-a406-6a8100cf8150. Nepoužít historický missing probe jako pozitivní fixture; žádné credentials v argv/evidence ani redirect přenos.
- V rámci zbývajících max. 12 GET naplánovat: bounded document-events discovery skutečného run/attempt; pages?attempt_no=… s nonempty PageCacheReused; run events pro stejnou identitu; případné jedno relevantní continuation okno; missing-key401, missing-Bearer403 a policy-odpovídající foreign-document404. Ověřit allowlisted JSON/cached fields/coverage, current scope, no content, private,no-store a actual deployed digest. Každý request předem i výsledkem evidovat; nepokračovat fill-loopem nebo vyčerpáním historie kvůli hledání fixture.
- Pokud první autorizované bounded okno nedodá důvěryhodný run/attempt/reuse, využít pouze doloženou existující syntetickou observation schválené provenance; bez ní uvést LIVE-FUNCTION-VERIFIED nesplněno. Žádné vymyšlené runy, audit/metadata seed, upload/replay, queue/lease zásah, placená inference ani grant widening. Výchozí plán syntetických writes = 0, každý případný podporovaný povolený write musí být předem konkrétně doložen a započten.

## Progress
- [x] Vytvořit canonical plán a prozkoumat aktuální kód, kontrakty, vlastní historický TDD a runtime evidence.
- [x] Zapracovat reuse hotové práce, TDD/regrese a guarded deploy/live kroky; žádnou implementaci ani cloud request v tomto plánování neprovést.
- [ ] Při implementaci dokončit SOURCE/INSTALLED ověření, skutečné nasazení a bounded live obsahovou větev nebo doložit konkrétní blocker.
