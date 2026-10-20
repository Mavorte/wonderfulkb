# Plan 2026-10-20: Monitoring MVP: jeden GET pozorovaných pokusů

## Analysis
- Reuse `processing_monitor_routes.authorized_document`, `read_authorized_window` a `AuditStore.read_document`; reader již dekóduje AttemptStarted a provádí jediný Query v EVENT#event_id pořadí, nikoli chronologii.
- Zachovat existující run-events cursor kompatibilitu a doplnit oddělenou operaci attempts se stejnou striktní validací.
- Zúžit pouze `AttemptObservation` v jediném YAML; nyní odkazuje na celý AttemptStarted envelope místo požadovaných tří polí.
- Navázat na `plans/monitoring/task-1d77ce99-3b09-48f7-9978-e0e99783c9b5-run-events-evidence.md`: poslední rollout je doložen dokončený, ale skutečná fixture membership/live obsah zůstávají nedoložené; znovu ověřit současný stav a ledger.
- Respektovat cizí staged/untracked změny; před implementací ověřit aktuální trigger diff a gate, historické konflikty nepovažovat bez fresh kontroly za současný blocker.
- Použít pravidla `learnings/architecture/2026-10-20_attemptstarted-audit-contract-preserves-producer-identity.md` a `2026-10-20_run-events-plan-reuses-document-reader-with-scoped-wrapper.md`: identitu dodává uložený event, nikoli receive count či business snapshot; pokračování obaluje existující reader token.
- Zohlednit recall výsledek `backend=local`, `collection=wonderfulkb-learnings`, diagnostic `Collection not found`; zachovat read-failure jako chybu podle `2026-10-19_monitoring-filereceived-audit-store-scope.md`.
- Vycházet z `be-intake/README.md`, `app/Dockerfile`, `template.yaml`, jediného YAML a `plans/handoffs/aws-runtime-readiness-20261020.md`; diagramy `**/*.puml` nenalezeny. Read compound-plan `scripts/plan-path.py` byl zamítnut; nepřekonávat denial jiným nástrojem. Kanonický helper se spustil úspěšně.
- Použít objevené skills `tdd` pro RED/GREEN, `validate-implementation` pro scope/API, `code-review` + `write-review-report` pro review, `acceptance` jen s dodaným manifestem a `save-learning` na závěr; připravený AWS access skill/reference načíst před runtime kroky.

## Approach
- Přidat GET `/v1/cases/{case_id}/processing/documents/{document_id}/runs/{run_id}/attempts` do existujícího routeru; facade ponechá jedinou implementaci auth/membership/no-store/error/read seamů.
- Jednou načíst `read_authorized_window`, filtrovat jen `AttemptStarted` s přesným `run_id`; vracet `{items,next_token,observed_at,coverage:"partial"}` s items přesně `{event_id,attempt_no,occurred_at}`. Nevyžadovat RunQueued ani další existence read runu; nepozorovaný run znamená prázdné okno, nikoli vymyšlenou existenci či úplnost.
- Zachovat pořadí vyhodnoceného okna a last-evaluated continuation včetně prázdné stránky; žádný Scan, fill-loop, agregace stránek, projekce, index, total/status/duration ani producer/business změna.
- Neopakovat stejnou idempotentní event identitu; různé event_id se stejným attempt_no ponechat jako oddělené observations, neslučovat je do business stavu. Reuse conditional put; nepřidávat globální dedup state ani snapshot záruku při refresh/replay tokenu.
- Sdílet striktní run cursor codec přes explicitní operation argument s výchozím `run_events`; attempts použije `attempts`. Zachovat stávající run-events bytes/validace a document token; outer scope = case/document/run/operation, inner token ověřit před Query. Odmítnout duplicitní JSON klíče, nekanonické encodingy, jinou operaci/scope, špatné typy a oversize.
## Implementation
1. Před produkčními změnami znovu přečíst tento plán, aktuální source/diff a případné vlastní proof/checkpoint/HTTP ledger; vytvořit focused test níže a zachytit skutečný RED pomocí `skill:tdd`. Ověřit venv dependencies/importy před capture; collection/import failure není RED.
2. V `processing_monitor_routes.py` rozšířit existující cursor codec a přidat attempts handler podle Approach; reuse `authorized_document`, `validate_identifier`, `read_authorized_window`, `PRIVATE`. Zachovat limit default50/range1–100, outer token max8192/inner4096 a bezpečný 503 při čtení/decode/DTO chybě. Neměnit ostatní připojené routes ani jejich guard politiku.
3. V jediném YAML upravit jen attempts operation/parametr tokenu a `AttemptObservation`: uzavřený objekt se třemi povinnými poli, pozitivním integer attempt_no a date-time occurred_at. Zkontrolovat účinné security vlastní operace proti prvnímu GET a opravit jen její deklaraci. Popsat partial/event-observation view, absenci RunQueued, konfliktní observations, technické pořadí a empty continuation. Zachovat obecný `AttemptStarted` a ostatní operace/DTO; přidat response-schema assertions do focused testu.
4. Zachytit matching GREEN a regresní gates; doplnit existující installed-image smoke o nonempty attempts DTO, odfiltrování druhého runu, empty continuation a cross-operation400. Pokud se mezitím objeví hotová route/proof, zachovat ji a nový RED omezit na skutečně chybějící chování; neodstraňovat funkci pro výrobu RED.
5. Založit append-only `plans/monitoring/task-dc9a8eab-2900-4aca-9a80-4411cebc0472-attempts-evidence.md`; zaznamenat source SHA256 včetně necommitnutých build vstupů, test/proof odkazy a účet/target/build owner. Před cloud akcemi načíst `skill:signing-in-to-aws` a jeho přesnou referenci; pro container kroky `skill:aws-containers`. AWS operace přednostně oficiálním MCP po signed STS pro účet609394381050/eu-central-1, kontrolovat `api_calls`; lokální SDK explicitně ai-hackathon/eu-central-1 dle příslušného SDK skillu. Žádné nové přihlášení bez doložené expirace.
6. Fresh DescribeService/ListOperations/ECR readback ověří jediný cíl `arn:aws:apprunner:eu-central-1:609394381050:service/wonderfulkb-ingest/c9ef96fae3da4192abd7e8280d43ae6b`, owner Jackie, aktuální image/index+amd64 manifest/config digest, operation/status a HTTPS host. Nepovažovat historický sibling rollout za nasazení nové attempts route. Reconcile existující sdílený HTTP/deploy ledger a zbývající budget před rezervací; vlastní ledger neobnovuje sourozenecké ani Case Client limity. Výchozí writes/POST/queue/inference/grant změny = 0; chybějící potvrzený zůstatek předat hostovi, neodhadovat jej.
7. Root build `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:task-dc9a8eab .` musí nainstalovat audit wheel. Ověřit wheel hash/verzi, importy a skutečný ASGI attempts handler jako UID10001 v final image bez sítě; porovnat všechny intake/audit source hashe s artifactem. Použít existující `image_processing_monitor_smoke.py`, nikoli další server. Případné chybějící COPY/permissions opravit pouze pro tento slice, znovu ověřit.
8. Před push/update uchovat skutečně dostupný recovery image manifest/digest a chráněný kompletní current config bez secret hodnot v repo evidence. Reuse owner postup z run-events evidence: existující ingest ECR, unikátní immutable candidate tag/digest, `shlock -p "$PPID" -f plans/monitoring/.intake-deployment.lock`; respektovat obsazený lock. Protože App Runner nemá atomický RevisionId, pod owner guardem bezprostředně znovu porovnat source/config/operation/status a abortovat při driftu či cizím rollout. Přes existující UpdateService změnit pouze ImageIdentifier ve fresh zachovaném SourceConfiguration; env/IAM/auth/network/health zachovat.
9. Rezervovat rollout v ledgeru před mutací, uložit operation ID/UTC časy, bounded poll nejvýše15min po15s do SUCCEEDED + RUNNING; poté znovu ověřit image tag→registry manifest/config digest a konfiguraci. Při timeoutu/ambiguous výsledku nejprve readback, nikoli další UpdateService. Při outage použít ověřený recovery pouze pod stále vlastněným guardem a beze změny cizí revize.
10. Před HTTP načíst v procesu aktuální API key/Bearer/policy ze tří přesných Secrets Manager names v access referenci; ověřit active token hash binding, explicitní grant a konzistentní membership `SYN-A01`/`34fcd896-107a-583f-a406-6a8100cf8150`. Referenční historická fixture naposledy vracela404: nepokračovat jako pozitivní fixture bez fresh důkazu. Žádné vypisování tokenů/hashů/policy ani redirect s credentials.
11. Pod zbývajícím ledgerem získat z autorizovaných document/run observations skutečné run_id a AttemptStarted event_id/attempt_no; bounded discovery neprocházet do úplné historie. S těmito ID provést skutečný autentizovaný HTTPS GET přímo attempts route, assertions dle Testing. Default cloud writes0: reuse doložené dřívější synthetic events; chybějící data neopravovat metadata insertem/audit seedem/replayem/queue send/provider voláním. Není-li bezpečná obsahová fixture, uvést konkrétní LIVE-FUNCTION-VERIFIED blocker a vyžádat přesný podporovaný operator krok v témže zadání.
12. Prověřit kompatibilitu skutečného writer/reader artifactu a audit schema přes native readiness handoff; chronologickou migraci, backfill/reset/Scan ani trigger konflikty tímto taskem neřešit. Potřebuje-li kompatibilita operator rozhodnutí, doložit přesný interface/schema/prerequisite. Chybějící producer není důkaz chyby GET ani důkaz live funkce.
13. Scope chyby routeru/package/DTO nalezené smoke opravit ve stejném tasku, znovu lokálně ověřit, guardovaně nasadit v dostupném budgetu a opakovat omezené assertiony. Skutečný permission/capacity/interface blocker předat Jackiemu s candidate digest, target/current revision-operation, přesným config diffem, recovery a zbývajícím nativním příkazem; následně doplnit ověření, neuzavřít source-only.
14. Použít `skill:validate-implementation`, `skill:code-review`, zakončit review `skill:write-review-report`; při dodaném manifestu také `skill:acceptance`. Zachovat historická selhání i registry gates. Evidence rozliší SOURCE / INSTALLED / DEPLOYED / LIVE-FUNCTION-VERIFIED; completion vyžaduje deployed+live obsahovou funkci. Poslední workflow akce: `skill:save-learning` a uložit konkrétní learning.

## TDD
Implementace TDD cyklu dle skill:tdd. Přidat `be-intake/tests/test_processing_monitor_attempt_routes.py`; reuse skutečné existující fixture/importy. Skeleton neprovádět během plánování:

```python
from test_monitor_file_received import intake  # noqa: F401
from test_processing_monitor_routes import monitor, event, get, RUN_URL  # noqa: F401

ATTEMPTS = RUN_URL.removesuffix("/events") + "/attempts"

def test_observed_attempts_without_run_queued(monitor):
    main, _, _, _, _, table = monitor
    table.query.return_value = {"Items": [
        event("a1", type="AttemptStarted", run_id="run-a", attempt_no=1),
        event("b1", type="AttemptStarted", run_id="run-b", attempt_no=1),
        event("a2", type="AttemptStarted", run_id="run-a", attempt_no=2),
        event("received"),
    ]}
    response = get(main, ATTEMPTS)
    assert response.status_code == 200  # RED: absent route returns 404
    assert response.json()["items"] == [
        {"event_id": "a1", "attempt_no": 1, "occurred_at": "2026-10-20T10:00:00Z"},
        {"event_id": "a2", "attempt_no": 2, "occurred_at": "2026-10-20T10:00:00Z"},
    ]
    assert response.json()["coverage"] == "partial"
    assert response.json()["next_token"] is None
    table.query.assert_called_once()
    table.scan.assert_not_called()
```

Spustit z root se stejným argv pro obě fáze:
```bash
TASK_ID=task-dc9a8eab-2900-4aca-9a80-4411cebc0472 python3 /Users/michal/.config/opencode/skills/tdd/scripts/proof-capture.py red -- env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_attempt_routes.py
TASK_ID=task-dc9a8eab-2900-4aca-9a80-4411cebc0472 python3 /Users/michal/.config/opencode/skills/tdd/scripts/proof-capture.py green -- env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests/test_processing_monitor_attempt_routes.py
```

| Test | RED | GREEN |
|---|---|---|
| `test_observed_attempts_without_run_queued` | autorizovaný GET404 místo200 | přesné dva DTO, cizí run/FileReceived vyloučen, jediný Query |

- Před RED doplnit do stejného souboru scénáře: unmatched první okno→empty+continuation→matched druhé okno, ExclusiveStartKey/Limit a právě1Query/request; obousměrné run-events/attempts/document token odmítnutí před Query; cizí case/document/run, malformed/duplicate/oversize token; limit0/101/bad→400.
- Před RED doplnit auth/revocation→403, missing/foreign document→404, required auth/membership/read/decode failure→503 a no-store/redacted error na každé odpovědi; reuse current policy fixture, žádný auth fallback. U distinct IDs stejného attempt_no ověřit zachování obou observations; store idempotence ověřit existujícím conditional-put testem, bez nového writeru.
- Vyžadovat canonical proof `plans/checkpoints/task-dc9a8eab-2900-4aca-9a80-4411cebc0472.red-green-proof.md` s accepted_red/accepted_green a nezměněným argv; proof ručně nepřepisovat.

## Testing
- Ověřit focused response proti skutečnému `AttemptCollection` v jediném YAML včetně nullable tokenu; negativně odmítnout extra status/total/duration, nulové/bool attempt_no a chybějící required pole. Ověřit UTC observed_at a nepřítomnost interního event envelope/content.
- Spustit `env PYTHONPATH=be-document-processing/src be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests`; zahrnuje FileReceived, run-events, audit idempotence a sole-contract regresi.
- Zachovat širší dosavadní gate: `env PYTHONPATH=be-document-processing/src:be-validator-agent/trigger:be-validator-agent/pipeline be-document-processing/.venv/bin/python -m pytest -q be-intake/tests be-document-processing/tests be-validator-agent/trigger/tests be-validator-agent/pipeline/tests`. Pre-existing trigger conflict/collection failure zaznamenat jako blocker, nevynechávat testy ani opravovat cizí scope.
- Spustit registrovaný gate přesně `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` (timeout300s) a `git diff --check`; neprohlašovat plánovací session za vykonání těchto gates.
- Installed image smoke spustit `docker run --rm --network none --user 10001 -i --entrypoint python wonderfulkb-ingest:task-dc9a8eab - < be-intake/tests/image_processing_monitor_smoke.py`; oddělit artifact-only fixture od AWS live evidence.
- Live HTTPS s oběma bezpečně načtenými headers ověří nonempty přesné známé event_id/attempt_no/occurred_at, žádný cizí run, partial/UTC/no-store a nepřítomnost business polí; kde skutečná fixture dovolí, limit1 continuation/empty continuation a cross-operation400. Ověřit aktuální auth/scope negativy podle reálné politiky; read503 pouze hermeticky, bez cloud fault injection.
- Do task evidence připsat čas, fixture case/document/observed run/event IDs, přesný počet requestů/writes, source/wheel/image digest a deployment operation/revision, bezpečné status/schema assertions a zbývající neověřené větve. Health200, empty200, auth404 ani lokální TestClient neoznačovat za live obsahový proof.

## Files
| Path | Planned change |
|---|---|
| `be-intake/app/processing_monitor_routes.py` | attempts GET, sdílený operation-bound run cursor codec; zachovat facade/ostatní handlers |
| `be-intake/tests/test_processing_monitor_attempt_routes.py` | nový focused HTTP/TDD/schema/isolation/continuation test |
| `be-intake/tests/image_processing_monitor_smoke.py` | rozšířit existující final-image ASGI assertions |
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | jen attempts operation/AttemptObservation DTO |
| `be-document-processing/src/document_processing/audit/audit_queries.py` | reuse beze změny; AttemptStarted decoding/one Query již existují |
| `be-intake/app/Dockerfile`, `be-intake/README.md` | pouze nutná packaging oprava či stručná dokumentace vlastní route |
| `plans/monitoring/task-dc9a8eab-2900-4aca-9a80-4411cebc0472-attempts-evidence.md` | skutečné test/install/deploy/live výsledky a append-only ledger |
| `plans/checkpoints/task-dc9a8eab-2900-4aca-9a80-4411cebc0472.red-green-proof.md` | helperem zachycený skutečný RED/GREEN |

## Progress
- [x] Opravit příčinu planning retry `invalid_header`: zachovat kanonickou cestu a použít H1 s prefixem `# Plan 2026-10-20:`; validovat H1 i přesný allowlist sekcí.
- [x] Přečíst stávající plán před revizí; znovu prověřit skutečné reader/router/test/DTO/build seams a access reference bez cloud requestů či implementace.
- [x] Prověřeny source seams, test fixtures, jediný YAML, build a poslední runtime evidence; kanonický plán uložen pro task-dc9a8eab-2900-4aca-9a80-4411cebc0472.
- [ ] Provést TDD implementaci a všechny registrované gates.
- [ ] Ověřit instalovaný artifact, guardovaně nasadit a doložit skutečný nonempty attempts HTTPS výsledek nebo konkrétní blocker.
- [ ] Dokončit review/acceptance dle manifestu a uložit learning při implementační dodávce.
