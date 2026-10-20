# Plan 2026-10-20: Monitoring MVP: jeden GET událostí konkrétního runu

## Analysis
- Při pokračování reuse již přítomné `run_events`, cursor wrapper a focused testy; nepřidávat route znovu. Zachovat existující pravý RED 404→200 a GREEN29 v `plans/checkpoints/task-1d77ce99-3b09-48f7-9978-e0e99783c9b5.red-green-proof.md`; nový RED vyžadovat pouze pro skutečně zjištěnou chybějící vlastnost.
- Reuse `processing_monitor_routes.py`: `authorized_document`, `read_authorized_window`, `event_dto`, `PRIVATE`; `AuditStore.read_document(case_id, document_id, limit, next_token)` již deleguje na jediný consistent document Query s `Limit` a `LastEvaluatedKey`.
- Zachovat document-events token version 1/operation `document_events` v `audit_queries.py`; run continuation obalit samostatným operation/run scope, nepřidávat druhý reader/store ani dotazování do naplnění stránky.
- Respektovat současnou SERVICE politiku v `processing_monitor_authorization.py`: missing/forged/revoked/ungranted case →403 před membership/audit I/O; missing/foreign document →404; selhání auth/membership/audit →503. Case existence ani upload key nejsou entitlement.
- Zachovat DTO `{items,next_token,observed_at,coverage:partial}` a existující safe event allowlist; run operation je už deklarovaná v jediném `be-document-processing/contracts/openapi-processing-monitor.yaml`.
- Převzít pravidla z learnings `2026-10-20_bounded-monitoring-read-plan-semantics.md` a `2026-10-20_monitoring-read-api-plan-scope.md`: cursor postupuje podle evaluated pozice, prázdná stránka může pokračovat, read failure není prázdný úspěch. Starší zákaz úprav YAML/deploy je pro tento task nahrazen aktuálním zadáním.
- Použít recall výsledek `backend=local`, `collection=wonderfulkb-learnings`, diagnostic `Collection not found`; relevantní vrácené FileReceived scope learnings zachovat pro bounded Query/error semantics, nikoli jejich historický zákaz HTTP/deploy.
- Navázat na `plans/monitoring/task-1d77ce99-3b09-48f7-9978-e0e99783c9b5-run-events-evidence.md`: poslední záznam uvádí UpdateService `e5bcdf6b57c74901a5befeb9678f8add` přijatý 2026-10-20T09:59:05Z, nikoli dokončený rollout. Při implementačním pokračování nejprve read-only ověřit jeho výsledek; žádný automatický opakovaný deploy.
- Použít existující Dockerfile/root build, ECR a native App Runner UpdateService; runtime readiness porovnat s `plans/handoffs/aws-runtime-readiness-20261020.md`, který uvádí dosud nekoordinovaný writer rollout a chybějící execution/audit env. Historické závěry znovu ověřit, žádné runtime tvrzení z tohoto plánování.
- Zachovat rozpracované shared source/YAML/ostatní routes. V repozitáři nejsou nalezeny `.puml`; nenavrhovat nový diagram ani doménové/schema rozšíření.

## Approach
- Reuse existující `GET /runs/{run_id}/events` na stávajícím `router` ve facade. Při nezbytném společném events/attempts oddělení použít pouze `processing_monitor_event_routes.py`, zachovat jednu shared auth/read implementaci a všechny route registrace.
- Po autorizaci a validaci run ID rozbalit přesný run-events cursor, zavolat jednou `read_authorized_window`, filtrovat `getattr(event, 'run_id', None) == run_id` a použít `event_dto`. FileReceived bez run identity vyloučit; nepoužívat page-observation mapper pro event timeline.
- Run token svázat s version, operation `run_events`, case_id, document_id, run_id a vnořeným document-reader tokenem; striktně kontrolovat shape, typy, encoding a délku. Převzít existující wrapper pattern pages/steps, ale neduplikovat Query nebo auth; definovat route-local délkový limit obalu 8192 a vnitřního tokenu 4096.
- Odmítnout cizí run/case/document/operation a poškozený cursor 400 před audit Query; vnořený reader token validovat existujícím seamem. Token není oprávnění; každá stránka opakuje current authorization/membership.
- Vrátit next_token z poslední vyhodnocené pozice i při nulovém počtu shod; nepozorovaný run vrací oprávněnou prázdnou kolekci 200/partial, nikoli tvrzení „run neexistuje“ nebo „historie kompletní“.
- Zachovat pravdivý současný kontrakt `EVENT#event_id`, nikoli deklarovat globální chronologii/snapshot. Pokud skutečný shared reader mezitím přejde na chronologický kontrakt, reuse jeho interface a ověřit kompatibilní writer i reader artifacty podle native trigger šablony/handoffu. Fyzickou schema/index/data migraci s rizikem ztráty předat ke konkrétnímu operator rozhodnutí; žádný automatický backfill/reset/Scan ani nový reader/index v tomto tasku.

## Implementation
1. Znovu zkontrolovat git diff, společné seams a task-local proof/evidence; načíst `skill:tdd` a připravit dependency prostředí. Implementace TDD cyklu dle skill:tdd: zachovat hotový pravý RED/GREEN, nejprve přidat failing regression jen pro nově doloženou chybu; nevypínat fungující route pro umělý RED. Další cykly ukládat odděleně s vazbou na původní proof.
2. Ověřit existující run route a scope wrapper proti níže uvedené matici; opravit jen doložený rozdíl po behaviorálním RED. Reuse `audit_queries.py`/`AuditStore`, shared chyby i DTO mapping503 a `private, no-store` pro všechny odpovědi přes existující middleware.
3. Úzce doplnit description/DTO vlastní run operation v jediném YAML: evaluated-window semantics, FileReceived exclusion, run-bound cursor, absent-run uncertainty, skutečná auth/status politika; zachovat ostatní operace, komponenty a dokončené změny. Ověřit skutečné odpovědi proti RunEventCollection/RunEvent schématům včetně nullable next_token pomocí stávajícího OpenAPI-aware patternu.
4. Doplnit testovací matici níže, zaznamenat GREEN a provést lokální gates. Použít `validate-implementation` a review s `write-review-report`; acceptance provést dle dodaného manifestu přes `acceptance`. Zachovat neúspěšné/předchozí evidence a zaznamenat případné souběžné nesouvisející failures.
5. Načíst `signing-in-to-aws` a přesný `references/wonderfulkb-test-access.md`; profil výhradně `ai-hackathon`, region `eu-central-1`, signed STS musí potvrdit účet `609394381050` (MCP také ověřit). Pro AWS preferovat MCP (`run_script`/presigned URL); pro container postup `aws-containers`, při psaní boto3 programu `aws-sdk-python-usage`. Ověřit TEST owner, ECR/App Runner, instance/access roles, env/auth references, tabulky, auto-deployment a operations; read není důkaz deploy oprávnění. Skutečný denial neobcházet, nový login jen při prokázané expiraci přes hosta s lidským potvrzením.
6. Před mutací uzamknout existující deployment postup a reconciliovat sdílené fixture/request/deploy ledgery. Uchovat ověřený immutable recovery image/digest a recoverable config, v evidence pouze redigované reference/hashes. Znovu porovnat aktuální service operation/revision/config hash bezprostředně před změnou; při driftu zastavit a znovu sladit owner stav. Neuvažovat, že App Runner má neexistující atomický revision parametr.
7. Porovnat aktuální source včetně untracked source s existujícím artifactem: candidate ECR tag `task-1d77ce99-e462d804`, index `sha256:e462d804b114d426df9d61e1b686f29afc07859ddd5ab3133dadb259585f9b8a`, amd64 manifest `sha256:99f39a86c78d8dbf6582d4accf082aa0f92af069fae29795d56a2c78154ad856`. Při změně source instalovat/build z rootu `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:task-1d77ce99 .`; Dockerfile staví a instaluje audit wheel `--no-deps`. Zaznamenat source/wheel/image digest, UID10001 a čitelné COPY každého nutného modulu.
8. Reuse již rozšířený `be-intake/tests/image_processing_monitor_smoke.py`; ověřit skutečný ASGI run GET v candidate image se stuby provider klientů, installed package/import/filter/cursor/no-store bez host PYTHONPATH, read-only mount a network-none. Nedeklarovat tento test jako live worker důkaz.
9. Nejdříve bounded poll již odeslané operace a porovnat runtime image/revision/digest s kandidátem. Nový immutable candidate publikovat a guarded in-place image-only update provést jen při nutné source opravě nebo prokázaném nenasaženém artifactu, ve zbývajícím budgetu. Zachovat env/IAM/auth; bounded wait do skutečného rollout completion/health s evidencí času/operation ID/digestu. Samotné přijetí deploy příkazu není úspěch.
10. Před HTTP načíst v paměti `wonderfulkb/ingest-api-key`→`x-api-key`, `wonderfulkb/monitoring-synthetic-bearer-20261020`→`Authorization: Bearer <token>` a samostatnou JSON policy `wonderfulkb/monitoring-synthetic-20261020`. Ověřit policy schema/hash/active/exaktní grant podle reference a current membership pro `SYN-A01`/`34fcd896-107a-583f-a406-6a8100cf8150`; run IDs získat jen z doložených observations. URL zjistit DescribeService pro ARN `arn:aws:apprunner:eu-central-1:609394381050:service/wonderfulkb-ingest/c9ef96fae3da4192abd7e8280d43ae6b`, credentials poslat pouze jeho ověřenému HTTPS hostu bez redirectů. Bez výpisu secrets/policy/headerů/obsahu; historický absent probe ani 200empty nejsou pozitivní fixture.
11. Pokračovat v existujícím ledgeru, nikoli resetovat budget: poslední evidence spotřebovala 1/2 forward rollout, 0/1 rollback, 0/20 live GET, 2/10 fixture reads a 0 writes/inference; před pokračováním započíst novější sdílené záznamy. Výchozí writes/inference zůstávají 0; reuse dřívější skutečný event bez replay. Bez podporované a konkrétně povolené bezpečné cesty nic neseedovat/nevkládat/neposílat do queue; chybějící obsahová fixture je blocker. Neměnit queue/lease/retry/granty, nevolat placené modely/downstream case processing ani neopakovat ambiguous non-idempotent request.
12. Autentizovaně ověřit přímo run-events URL: konkrétní očekávaný event_id/type/run_id/case/document, bezpečný DTO/schema, observed_at UTC, coverage partial, private/no-store, vyloučení jiného runu/FileReceived, continuation a cross-run token400 kde fixture umožní, missing auth403 a scope404 dle current policy. Zkontrolovat stávající document FileReceived GET. Pouhé health/200empty nestačí; bez relevantního skutečného eventu vykázat DEPLOYED, ale LIVE-FUNCTION-VERIFIED neověřené.
13. Vlastní package/router/DTO chyby opravit v tomto scope přes testy, nový digest, guarded redeploy a omezený smoke ve zbývajícím budgetu. Při outage použít ověřený rollback pouze pokud stále vlastníme aktuální revision; nepřepsat cizí mezitím nasazenou image.
14. Při nedostupném deploy oprávnění/rozhraní předat Jackiemu v tomto tasku přesný target, artifact digest, minimální config diff, recovery reference, guard a zbývající owner krok; po jeho provedení doplnit HTTP verification. Do `plans/monitoring/task-1d77ce99-3b09-48f7-9978-e0e99783c9b5-run-events-evidence.md` uložit příkazy/výsledky, source/wheel/image hashes, revision/operation/time, fixture IDs/request counts, schema/status assertions, opravy/rollback/blocker a samostatné SOURCE/INSTALLED/DEPLOYED/LIVE-FUNCTION-VERIFIED; žádné credentials/policy bodies/document content. Nakonec použít `save-learning`.

## TDD
- **Soubor:** `be-intake/tests/test_processing_monitor_routes.py`; reuse test za prvním events GET a skutečné `monitor`, `get`, `event`, `URL` fixtures/helpers. Skeleton níže je již implementovaný regression test; znovu jej nevkládat.
- **Run command:** `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_routes.py -k run_events`
- **Preflight:** zajistit instalovaný interní package a test dependencies; import/collection chyba není RED. Původní behaviorální RED chybějící route404 a GREEN29 již existují; zachovat je, pro každou novou opravu vytvořit nový focused RED/GREEN přes skill:tdd bez přepsání historie.

```python
def test_run_events_continue_across_unmatched_window(monitor):
    from document_processing.audit.audit_queries import document_key
    main, _, _, _, _, table = monitor
    key = {"pk": document_key("case-test", "doc-test"), "sk": "EVENT#other"}
    table.query.side_effect = [
        {"Items": [event("received"), event("other", type="RunQueued", run_id="run-b")],
         "LastEvaluatedKey": key},
        {"Items": [event("wanted", type="RunQueued", run_id="run-a")]},
    ]
    url = URL.removesuffix("/events") + "/runs/run-a/events"
    first = get(main, url, params={"limit": 2})
    assert first.status_code == 200  # RED: absent run-events route is not 200
    assert first.json()["items"] == []
    assert first.json()["coverage"] == "partial"
    token = first.json()["next_token"]
    assert token
    assert table.query.call_count == 1
    assert table.query.call_args.kwargs["Limit"] == 2
    second = get(main, url, params={"limit": 2, "next_token": token})
    assert second.status_code == 200
    assert [item["event_id"] for item in second.json()["items"]] == ["wanted"]
    assert second.json()["next_token"] is None
    assert table.query.call_args.kwargs["ExclusiveStartKey"] == key
    assert table.query.call_count == 2
    denied = get(main, url.replace("run-a", "run-b"), params={"next_token": token})
    assert denied.status_code == 400
    assert table.query.call_count == 2
    table.scan.assert_not_called()
```

| Test | RED | GREEN |
|---|---|---|
| `test_run_events_continue_across_unmatched_window` | Chybějící run route vrátí non-200 | Empty+token; další stránka wanted; 1 Query/request; cross-run400 bez Query |
| Reuse `test_run_events_filter_and_document_parity` | Původní chybějící route | Mixed FileReceived + dva runy: pouze požadovaný run; document GET obsahuje FileReceived |
| Reuse `test_run_events_cursor_scope` | Původní chybějící route/validace | Cross-case/document/operation, malformed/oversize token400; žádná ztráta mezi evaluated okny |
| Reuse `test_run_events_auth_scope_and_read_failure` | Původní chybějící route | Oprávněný200; bez/forged/revoked grant403 před I/O; missing/foreign document404; auth/membership/read/decode/DTO failure503 |
| Reuse a případně rozšířit `test_run_events_limits_unknown_and_contract` | Nový RED jen při prokázaném DTO driftu | Limit1/100, invalid400; nepozorovaný run200 partial; nullable next_token, observed_at a relevantní RunEvent varianty dle YAML |

## Testing
- Při implementaci použít `tdd`, po změnách `validate-implementation`, review zakončit `write-review-report`; `acceptance` použít jen proti skutečně dodanému run manifestu. `save-learning` spustit jako poslední dokončovací krok; plánovací běh neprovádí implementaci/test rollout ani nefinalizuje runtime acceptance.
- Spustit focused command přes canonical RED/GREEN capture dle `skill:tdd`; neměnit hotovou implementaci kvůli umělému RED, pokud mezitím route dodá jiný task, doložit aktuální genuine missing behavior.
- Spustit `be-document-processing/.venv/bin/python -m pytest -q be-intake/tests` a `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests`; zachovat document/auth/page/step/lifecycle regressions a všechny existující assertions.
- Spustit širší stávající gate `PYTHONPATH=be-validator-agent/trigger:be-validator-agent/pipeline be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests be-validator-agent/trigger/tests be-validator-agent/pipeline/tests`; nesouvisející failures vykázat, ne skrýt ignores.
- Zachovat registrovaný gate přesně: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; následně `git diff --check`.
- Ověřit built-image route smoke, sole OpenAPI semantic/schema testy, guarded rollout a skutečný authenticated run GET podle kroků 7–12; read failure503 zkoušet hermeticky bez cloud fault injection.

## Files
| Cesta | Plánovaná změna |
|---|---|
| `be-intake/app/processing_monitor_routes.py` | Run-events route, scoped cursor a reuse sdílených auth/read/DTO helperů |
| `be-intake/tests/test_processing_monitor_routes.py` | Focused run-events TDD a document GET regression/schema assertions |
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | Pouze vlastní run operation/DTO upřesnění, ostatní zachovat |
| `be-intake/tests/image_processing_monitor_smoke.py` | Installed-image run-events funkční smoke |
| `be-intake/README.md` | Popsat novou route a přesnou bounded/auth/token semantiku |
| `be-document-processing/src/document_processing/audit/audit_queries.py` | Reuse existující token/Query kontrakt; úprava jen pokud test doloží nezbytný sdílený seam, žádný nový reader |
| `plans/monitoring/task-1d77ce99-3b09-48f7-9978-e0e99783c9b5-run-events-evidence.md` | Task-local lokální/artifact/deploy/live evidence a request ledger |
| `plans/checkpoints/task-1d77ce99-3b09-48f7-9978-e0e99783c9b5.red-green-proof.md` | Canonical TDD evidence spravovaná skill:tdd |

## Progress
- [x] Uložit plán do kanonické cesty a prozkoumat shared reader/auth/router/YAML/image/deployment evidence.
- [x] Aktualizovat plán podle existujícího RED/GREEN, artifactu a odeslaného, dosud neattestovaného rolloutu; aktuální cloud stav ověřit až při implementaci.
- [ ] Při implementaci ověřit stávající proof/artifact/gates a doplnit případné genuine opravy přes skill:tdd.
- [ ] Doložit skutečný guarded deployment a funkční authenticated HTTP nebo konkrétní blocker; dokončit review/acceptance a uložit learning.
