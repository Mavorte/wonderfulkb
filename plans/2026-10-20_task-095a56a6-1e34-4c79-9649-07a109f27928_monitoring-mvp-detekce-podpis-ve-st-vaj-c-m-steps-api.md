# Plan 2026-10-20: Monitoring MVP: detekce podpisů ve stávajícím steps API

## Analysis
- Rozšířit `OBSERVATION_FIELDS` v existujícím `processing_monitor_step_routes.py`; `signature_detection` store již dekóduje, ale steps jej nyní zahazuje.
- Ověřit veřejný failure kód: sdílený `PUBLIC_ERROR_CODES["StepFailed"]` zatím převádí `SIGNATURE_DETECTION_FAILED` na `PROCESSING_FAILED`; document/run events již existují a sdílejí `event_dto`.
- Zachovat jediný `read_document` Query s evaluated limit/LastEvaluatedKey; dnešní reader řadí `EVENT#event_id`, ne chronologicky. Kompatibilitu writer/reader ověřit přes existující runtime handoff, bez lokálního přestavování readeru.
- Před implementací znovu ověřit pracovní strom a vlastnictví sdílených změn; nebalit slepě cizí rozpracované soubory. Dříve zaznamenané konflikty nepovažovat bez aktuální kontroly za trvající.

- Řídit se `slice-signatures` v `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a kontrakty `plans/tasks/2026-10-20_monitor-mvp-{18-signature-events,11-attempt-steps-get}.md`; nepřidávat producer hook ani detekční logiku.
- Použít learnings `learnings/architecture/2026-10-20_extraction-steps-allowlist-and-run-events-prerequisite.md` s aktualizací podle dnešního source (run-events již existuje) a `learnings/tooling/2026-10-20_extraction-read-plan-resumes-source-proof-and-runtime-ledger.md`: zachovat skutečné důkazy, žádný umělý RED ani reset budgetu. Recall: backend `local`, collection `wonderfulkb-learnings`, diagnostic `Collection not found`; fallback není blocker.
- Navázat na `plans/monitoring/task-12f46945-d733-47dc-b0e9-b8c9746fd7c2-runtime-evidence.md`, cache-read evidence a `plans/handoffs/aws-runtime-readiness-20261020.md`; historická chybějící membership/observations a nepřevzatý guard vyžadují čerstvý preflight, nejsou současným cloud měřením tohoto plánu.
- Při předání ověřit canonical artifact validátorem první řádek `# Plan 2026-10-20:` a nezávisle každý nadpis proti sedmi povoleným sekcím; předchozí `invalid_header` neopravovat změnou task briefu ani přejmenováním plánu.

## Approach
- Přidat tři dvojice `(StepStarted|StepFinished|StepFailed, signature_detection)` do existujícího `OBSERVATION_FIELDS`, se stejnými `FACT_FIELDS` a jen doloženým `duration_ms`/`error_code`. Zachovat sdílené mapování a page delegaci.
- V `processing_monitor_routes.py` změnit pouze nezbytný veřejný allowlist failure kódu; document/run events reuse `event_dto`, žádný nový endpoint ani paralelní mapper. Case/document envelope events zachovat podle jejich kontraktu.
- Vrátit terminal-only fragment bez start/run události; returned-failed reprezentovat uloženým StepFailed, completed-empty uloženým StepFinished. Disabled/absent/start-only nic nesyntetizuje: žádný status, skipped, counts, historická konfigurace nebo model-call tvrzení.
- Zachovat `items,next_token,observed_at,coverage=partial`, jeden bounded evaluated dokumentový Query a filtr run/attempt v existujícím step adapteru. Token váže case/document/run/operation=steps/attempt a poslední evaluated pozici; prázdné items s continuation jsou platné. Žádné Scan/fill loop/párování historie/projekce/latest claim.
- V jediném YAML doplnit tři uzavřené non-page signature observation větve do `StepObservation`, povolený veřejný failure kód a text existujících dotčených GET; zachovat ostatní operace a page scope.

## Implementation
1. Před produkční editací načíst `skill:tdd`, ověřit importy existujícího Python prostředí a zachytit focused RED níže; případné již hotové větve charakterizovat bez odstraňování implementace. Použít vlastní task ID a uchovat kanonický proof i předchozí neúspěchy.
2. Provést pouze allowlist/DTO/YAML diff z Approach; `audit_queries.py`, auth a main registraci ponechat na existujících rozhraních. Chybějící nutný seam doložit konkrétním interfacem/blockerem, nevytvářet druhý reader nebo fake auth.
3. Doplnit focused HTTP a kontraktové scénáře z Testing, ověřit GREEN stejným argv, spustit regrese a registrovaný gate; zjištěné vlastní chyby opravit ve stejném scope.
4. Rozšířit `be-intake/tests/image_processing_monitor_smoke.py` o neprázdný signature terminal/failure přes nainstalovaný FastAPI/router a document/run parity; zachovat cizí assertions. Použít native root-context build:
   `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:signature-task-095a56a6 .`
   a `docker run --rm -i --platform linux/amd64 --user 10001 --network none --entrypoint python wonderfulkb-ingest:signature-task-095a56a6 - < be-intake/tests/image_processing_monitor_smoke.py`.
   Ověřit skutečný non-editable audit wheel v site-packages, importy bez source mount/PYTHONPATH, hash wheelu, scoped source manifest, image index/platform manifest/config digest; Dockerfile už wheel instaluje a step router kopíruje, měnit jej jen při doložené packaging chybě.
5. Pro runtime načíst `signing-in-to-aws` a jeho `references/wonderfulkb-test-access.md` (při plánování čitelné), při AWS container práci `aws-containers`. Ověřit signed STS pro `ai-hackathon`, `eu-central-1`, účet `609394381050`; preferovat AWS MCP se stejnou ověřenou identitou, kontrolovat skutečné `api_calls`. AWS CLI přes Bash nepoužívat; podporované local build/push kroky ponechat existujícímu ownerovi, pokud potřebný interface není dostupný.
6. Čerstvě prověřit owner/DescribeService/ListOperations/ECR/config a kompatibilní audit writer/reader artifacts podle runtime handoff. Cíl je `arn:aws:apprunner:eu-central-1:609394381050:service/wonderfulkb-ingest/c9ef96fae3da4192abd7e8280d43ae6b`; endpoint zjistit DescribeService. Převzít existující `.intake-deployment.lock`/owner guard a sdílený deploy+HTTP ledger; samotný mrtvý PID není převod vlastnictví. Zachovat case-client budget, žádný reset ani předpoklad volné kapacity.
7. Před mutací uchovat ověřenou recovery image a chráněnou config kopii bez secret hodnot v evidenci; porovnat source manifest po buildu i těsně před nasazením. Použít existující ECR/native App Runner postup doložený run-events/extraction evidencí, žádný nový deploy framework. Očekávaný diff pouze image reference ve fresh SourceConfiguration, se zachováním env/IAM/auth/health/auto-deploy. App Runner nemá CAS RevisionId: použít owner lock a fresh operation/image/config comparison; při driftu abort.
8. Nasadit ověřený artifact in-place v rámci převzatého zbytku budgetu; bounded poll maximálně 15 minut/15 sekund a nejvýše min(zbytek sdíleného budgetu, 2 candidate rollouts + 1 recovery). Ověřit operation SUCCEEDED, RUNNING, skutečný image/platform digest/config a časy operace, nejen přijetí update. Při outage použít recovery pouze proti vlastní nezměněné revizi; cizí revizi nepřepisovat. Fyzické schema/index změny, backfill/reset a worker rollout neprovádět tímto read patchem; nekompatibilitu předat existujícímu runtime ownerovi v témže delivery.
9. V paměti načíst Secrets Manager `wonderfulkb/ingest-api-key`, `wonderfulkb/monitoring-synthetic-bearer-20261020` a policy `wonderfulkb/monitoring-synthetic-20261020`; ověřit aktuální schema, SHA256 binding, active state, exaktní grant a skutečnou membership pro `SYN-A01`/`34fcd896-107a-583f-a406-6a8100cf8150`. Poslat oba headers jen na ověřený HTTPS host bez redirects. Žádné secrets v argv/souborech/chat/raw dumpech; denial zachovat bez bypassu.
10. Rezervovat HTTP requests předem ze skutečného zbývajícího ledgeru (nejvýše min(zbytek, 12 GET), žádný automatický retry). Bounded document-events discovery použít k doložení reálného run/attempt a signature event ID; přímo ověřit změněné steps DTO, document/run parity, pages exclusion, relevantní continuation, auth/scope a private,no-store podle Testing. Neprocházet historii do naplnění ani používat vymyšlené run IDs. Preferovat existující doloženou syntetickou observation; plán nevyžaduje žádný cloud write pro fixture. Chybějící fixture řešit pouze podporovanou konkrétně povolenou cestou přes ownera, bez metadata/audit seed, upload/replay, inference, queue/lease/retry zásahů nebo grant widening.
11. Ukládat task evidence do `plans/monitoring/task-095a56a6-1e34-4c79-9649-07a109f27928-signature-read-evidence.md`: source/wheel/image digests, target revision/operation+čas, install/deploy kroky, fixture/case/event/run/attempt IDs, přesné počty read/write/HTTP requests, bezpečné status/schema/scoping assertions a chyby/opravy/rollback. Rozlišit SOURCE / INSTALLED / DEPLOYED / LIVE-FUNCTION-VERIFIED; 200empty, 404, health ani hermetický image smoke nejsou pozitivní signature live proof.
12. Při skutečném permission/capacity/interface/fixture blockeru předat Jackiemu v témže zadání přesný dostupný artifact digest, target, config diff, recovery, guard a zbývající native krok; po jeho provedení doplnit skutečné readback/HTTP ověření. Neuzavírat source-only ani odkládat smoke na nový task. Scope opravy znovu lokálně ověřit, guardovaně nasadit a bounded smoke zopakovat ze zbývajícího budgetu.
13. Použít `validate-implementation`, `code-review` a na konci review `write-review-report`; acceptance provést přes `acceptance`, až bude dodán manifest, bez přepisování historie/gates. Na konci implementační dodávky spustit `save-learning` a zaznamenat pravdivý výsledný runtime stav.

## TDD
Implementace TDD cyklu dle skill:tdd. Nový soubor `be-intake/tests/test_processing_monitor_signature_observations.py`; reálné fixtures explicitně importovat jako v `be-intake/tests/test_processing_monitor_extraction.py`. První změna implementační fáze je test, ne produkční allowlist.

```python
import pytest
from fastapi.testclient import TestClient
from test_monitor_file_received import intake  # noqa: F401
from test_processing_monitor_routes import monitor, HEADERS, event

BASE = "/v1/cases/case-test/processing/documents/doc-test"

@pytest.mark.parametrize("kind", ["StepStarted", "StepFinished", "StepFailed"])
def test_signature_terminal_fragment_and_event_parity(monitor, kind):
    main, _, _, _, _, table = monitor
    extra = {"error_code": "SIGNATURE_DETECTION_FAILED"} if kind == "StepFailed" else {}
    table.query.return_value = {"Items": [event(
        "signature-observed", type=kind, sequence=7, run_id="run-test",
        attempt_no=1, stage="signature_detection", **extra)]}
    paths = [BASE + "/runs/run-test/steps?attempt_no=1",
             BASE + "/events", BASE + "/runs/run-test/events"]
    with TestClient(main.app) as client:
        responses = [client.get(path, headers=HEADERS) for path in paths]
    for response in responses:
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        body = response.json()
        assert body["coverage"] == "partial"
        assert [item["event_id"] for item in body["items"]] == ["signature-observed"]
        assert body["items"][0]["type"] == kind
        assert body["items"][0]["stage"] == "signature_detection"
        assert "page_number" not in body["items"][0]
        if extra:
            assert body["items"][0]["error_code"] == extra["error_code"]
    assert table.query.call_count == 3
    table.scan.assert_not_called()
```

Focused argv z rootu pro shodný RED/GREEN:
`env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_signature_observations.py`

| Skeleton test | Expected RED | Expected GREEN |
|---|---|---|
| StepStarted / StepFinished / StepFailed | HTTP200, steps items=[] místo skutečné observation | Přesně jeden původní event, bez nutnosti start/run eventu |
| StepFailed parity | Po samostatném ověření events: kód PROCESSING_FAILED místo SIGNATURE_DETECTION_FAILED | Stejný uložený bezpečný kód ve všech třech views |

Uchovat helper-generated proof `plans/checkpoints/task-095a56a6-1e34-4c79-9649-07a109f27928.red-green-proof.md`; přečíst accepted RED před produkční editací. Collection/import/auth/test-expectation chyba není behaviorální RED; dodatečné scénáře nepřipisovat původnímu cyklu.

## Testing
- Doplnit completed-empty/start+finish, returned-failed i raised-failed jako uložený StepFailed, terminal-only s/bez duration, start-only, disabled/absent bez observations; netvrdit skutečné volání detectoru nebo z counts odvozovat outcome.
- Ověřit přesné povolené klíče a finite nezáporný duration/safe code; zakázat signature hodnoty, citace, geometry, findings/counts/results/config, raw errors, status/model-call tvrzení. Validovat skutečné JSON proti OAS30Validator sole YAML a negativně odmítnout extra properties/page_number.
- Ověřit run/attempt izolaci, foreign case/document scope, neprázdný i prázdný evaluated window s continuation, přesný Limit/ExclusiveStartKey a právě jeden Query/request, žádný Scan/doplňovací read; cross-case/document/run/operation/attempt a malformed token odmítnout bez Query navíc.
- Reuse skutečný authorization seam: missing/forged/revoked/ungranted403, missing/foreign document404, required auth/membership/audit/decode failure503, bad attempt/token400 a private,no-store včetně chyb. Shared key sám nepřiznává case práva; podle deployed outer guard ověřit i chybějící API key401. Read503 pouze hermeticky, bez fault injection.
- Ověřit signature ID/type/duration/error parity steps vs document/run events; pages neobsahuje non-page stage; zachovat source/extraction/page/cache/attempts/lifecycle GET regrese.
- Spustit `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests` včetně `test_monitor_signature_events.py` a `test_monitor_openapi_observation_contract.py`.
- Zachovat přesný registrovaný gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` (timeout 300 s, failAction followup); spustit `git diff --check` a zaznamenat skutečné unrelated conflict/gate blokery bez jejich mazání.
- Po deploy požadovat neprázdnou skutečnou signature observation přes changed GET s doloženým run/attempt a schema/scoping/no-store assertions. Při prázdné audit partition nebo chybějící membership výslovně ponechat LIVE-FUNCTION-VERIFIED nesplněno; dřívější worker/hook source není live proof.

## Files
| Cesta | Plánovaný diff |
|---|---|
| `be-intake/app/processing_monitor_step_routes.py` | Tři signature stage/type allowlist položky v existujícím mapperu |
| `be-intake/app/processing_monitor_routes.py` | Pouze zachování bezpečného signature failure kódu v public DTO |
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | Signature StepObservation větve, failure enum a dotčené GET semantics |
| `be-intake/tests/test_processing_monitor_signature_observations.py` | Nové focused FastAPI/fake/schema testy s reuse fixtures |
| `be-intake/tests/image_processing_monitor_smoke.py` | Signature assertions nad skutečným nainstalovaným image |
| `plans/monitoring/task-095a56a6-1e34-4c79-9649-07a109f27928-signature-read-evidence.md` | Task-local instalační/deploy/live ledger a konkrétní blockers |
| `plans/checkpoints/task-095a56a6-1e34-4c79-9649-07a109f27928.red-green-proof.md` | Kanonický důkaz generovaný TDD helperem |

## Progress
- [x] Obnovit stejný kanonický plán, opravit povinný H1 prefix a znovu prověřit router/DTO/reader, sole YAML, kontrakty, fixtures a runtime handoff.
- [ ] Implementační fáze: zachytit genuine RED, provést úzký diff a ověřit GREEN/regrese/gates.
- [ ] Instalovat artifact, převzít guard/ledger, guardovaně nasadit a doložit pozitivní live signature HTTP větev nebo konkrétní blocker v témže delivery.
- [ ] Dokončit review/acceptance/evidence a uložit implementační learnings.
