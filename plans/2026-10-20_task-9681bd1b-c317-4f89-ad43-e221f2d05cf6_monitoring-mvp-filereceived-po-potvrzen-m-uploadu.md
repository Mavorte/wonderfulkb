# Plan 2026-10-20: Monitoring MVP: FileReceived po potvrzeném uploadu

## Progress
- [x] Založit kanonický plán pro task-9681bd1b-c317-4f89-ad43-e221f2d05cf6.
- [x] Opravit příčinu `invalid_header`: první řádek musí začínat `# Plan YYYY-MM-DD:`; zachovat původní kanonický soubor.
- [x] Ověřit commit hranici, audit store, balení a projektové poznatky.
- [x] Doplnit konkrétní implementační kroky, TDD a ověřovací příkazy.
- [x] Ověřit `inspect_plan_artifact`: `valid`, kanonický přímý potomek `plans/`; všech sedm `##` nadpisů odpovídá allowlistu, bez status/WIP/TODO markerů.
- [ ] Implementovat podle tohoto plánu v navazujícím běhu; nyní vzniká pouze plán.

## Analysis
- V `main.py:223–243` zachytit přesný `todo` až při úspěšném návratu transakce; `items` zahrnuje i řádky prohrané vůči souběžnému požadavku.
- Reuse `AuditStore.put(FileReceived)`; store již izoluje serializaci/persistenci, ale tvorba eventu musí být uvnitř nové listener boundary. Zachovat `AUDIT_TABLE_NAME`, connect/read timeout 1/2 s a `total_max_attempts=1`.
- Respektovat sedmipolovou obálku, klíč `EVENT#{event_id}` a dokumentový partition key; stabilní identitu neodvozovat od sequence/času.
- Přestavět Docker context: dnešní `be-intake/app/Dockerfile` kopíruje jen requirements/main; package deklaruje setuptools distribuci `wonderfulkb-document-processing`.
- Zachovat existující necommitnutý audit store, IAM a návrhové dokumenty; nepřepisovat je jako vlastní práci.
- Použít `plans/monitoring/mvp-reference-20261019.md:18` a proposal sekci `Izolace implementace` jako autoritu pro hook a injekci.
- Aplikovat learnings o stabilní identitě a skutečném implementation-specific RED; recall backend `local`, collection `wonderfulkb-learnings`, diagnostic `Collection not found`.
- Při implementaci použít `skill:tdd` pro RED/GREEN, `skill:validate-implementation` pro finální kontrolu a `skill:save-learning` pro poznatek; discovery skillů již proveden jednou.

## Approach
- Definovat v `audit/audit_listener.py` malý `AuditListener` protokol s `file_received(*, case_id: str, document_id: str, occurred_at: str) -> None`, `NoOpAudit` a fail-open implementací; všechny auditní importy storage/event DTO ponechat uvnitř package.
- Zapojit listener factory v composition části `main.py` do `app.state.audit_listener`; upload získá `Request` a předá listeneru pouze tři skaláry z potvrzeného řádku. `app.state` použít jako injekci závislosti, nikoli request/event context.
- Factory, konstrukci/validaci eventu, serializaci i sink volání izolovat v audit package; do business toku nepřidávat auditní try/except, retry, DTO, kopie dokumentů ani novou business funkci.
- Odvodit `event_id` jako UUIDv5 s pevným namespace `uuid.NAMESPACE_URL` a JSON `["wonderfulkb.audit.v1", "FileReceived", case_id, document_id]` (`ensure_ascii=True`, `separators=(",", ":")`); použít `sequence=0`, `schema_version=1`, `type="FileReceived"`, původní `received_at`. Identitu nezávislou na čase a sequence ověřit testem a zapsat do handoff.
- Zachovat best-effort význam: jeden pokus o audit na nově potvrzený dokument, conditional store maximálně jeden uložený event; při výpadku může event chybět a duplicate jej nedoplňuje.
- Omezit dodávku na hook, interní listener, lokální balení a handoff; HTTP router, worker/queue, jiné eventy a deployment do tohoto plánu nezahrnovat.

## Implementation
1. Použít `skill:tdd`: nejprve přidat níže uvedený test do nového `be-intake/tests/test_monitor_file_received.py`, zachytit skutečné RED na chybějícím post-commit volání a teprve potom upravovat produkční kód. Vyřešit collection/dependency chyby před zachycením RED.
2. Přidat protokol, `NoOpAudit`, konkrétní listener a `from_env` factory do `audit_listener.py`. Obalit celé vytvoření identity/eventu i `store.put` jednou fail-open hranicí; nepropouštět výjimky a nelogovat payload/raw výjimky. Reuse `AuditStore.from_env()` a jeho konečné SDK timeouty bez retry; disabled konfiguraci řešit NoOp.
3. V `main.py` inicializovat prázdný seznam potvrzených řádků před commit smyčkou. Ihned po úspěšném `transact_write_items` uložit přesný aktuální `todo`; po opuštění smyčky zavolat listener jednou na každý z těchto řádků a před sestavením stávající odpovědi. Při empty todo či výjimce neemitovat. Zachovat tři business pokusy, podmínky, pořadí S3→metadata, statusy i duplicate návrat.
4. Doplnit cílené caller testy na duplicate uvnitř requestu/opakovaný request, úplnou prohru souběhu a smíšený winner+nový dokument po retry. Vyžadovat event pouze pro vlastní úspěšné `todo`; pro metadata/S3 failure žádný event.
5. Ověřit caller diferenciálně s NoOp, funkčním listenerem a listenerem se selhávajícím sinkem: shodné business writes i pořadí, počty S3/metadata volání, status/body nebo původní chybu. V listener testu injektovat chybu event factory, `to_item` a sinku; žádný business catch ani opakovaný audit pokus.
6. Upravit existující Dockerfile na build z kořene repa: builder vytvoří wheel distribuce `wonderfulkb-document-processing` z jejího `pyproject.toml`; runtime nainstaluje stávající intake requirements a wheel přes `pip install --no-deps`. Nekopírovat audit zdroj do intake ani do `/app`; builder kopíruje pouze metadata/requirements a `src` interního package. Ponechat runtime user/port/CMD. Celé document-processing závislosti neinstalovat: jejich FastAPI/boto3 piny kolidují s intake; audit potřebuje jen již instalované boto3/botocore a stdlib. Smoke ověří tuto konkrétní runtime kombinaci.
7. Jako existující build entrypoint použít upravený `be-intake/app/Dockerfile`; do `be-intake/README.md` přidat root-context příkaz (dnes build instrukci neobsahuje). Před změnou prohledat existující CI/scripts callery Dockerfile a upravit případný app-only context na root context; nevytvářet nový build/deploy framework.
8. V `be-intake/template.yaml` navázat audit policy ARN na parametr `AuditTableName` s dosavadním názvem jako defaultem; zachovat nynější PutItem/Query rozsah pouze této tabulky a ostatní business oprávnění. Tabulka i její outputs již existují v `documents-table/template.yaml`: nevytvářet druhou tabulku a neměnit business schéma. Protože tato šablona nedefinuje App Runner service/env, uvést v handoff explicitní budoucí mapování `AUDIT_TABLE_NAME` na tento název, nikoli předstírat nakonfigurovaný runtime.
9. Vytvořit `plans/monitoring/file-received-build-contract.md`: podpis listener/store (`put` vrací inserted/duplicate/disabled/unavailable), sedm polí, event identity+namespace, `AUDIT_TABLE_NAME`, timeout/no-retry, root-context build a image import příkaz, image ID a skutečné výsledky. Ověření označit jako lokální; neskrývat blokery a netvrdit deployment.

## Files
| Path | Concrete change |
|---|---|
| `be-document-processing/src/document_processing/audit/audit_listener.py` | Nový protokol, NoOp, fail-open listener/factory a stabilní identita. |
| `be-intake/app/main.py` | Composition injection + přesná post-commit sada a třískalárové volání. |
| `be-intake/app/Dockerfile` | Root-context wheel build a skutečná non-editable instalace package. |
| `be-intake/README.md` | Aktualizovat existující build instrukci. |
| `be-intake/template.yaml` | Audit table parameter a scoped ARN bez business změn. |
| `be-intake/tests/test_monitor_file_received.py` | Nové focused HTTP/caller/differential testy. |
| `be-intake/tests/test_audit_listener.py` | Nové focused identity a fail-open boundary testy bez těžkého processing conftest. |
| `plans/monitoring/file-received-build-contract.md` | Krátký ověřený build/store/config handoff. |

## TDD
- Implementace TDD cyklu dle `skill:tdd`; uložit RED/GREEN důkaz do `plans/checkpoints/task-9681bd1b-c317-4f89-ad43-e221f2d05cf6.red-green-proof.md`.
- Vytvořit nový `be-intake/tests/test_monitor_file_received.py` s následujícím spustitelným skeletonem; testuje skutečný FastAPI upload, boto klienty nahrazuje jen na I/O hranici. Neprovádět AWS volání.
- Spustit z kořene: `PYTHONPATH=be-document-processing/src python3 -m pytest -q be-intake/tests/test_monitor_file_received.py -k new_upload`.

```python
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import boto3
from fastapi.testclient import TestClient


def test_new_upload_emits_once_after_commit(monkeypatch):
    for key, value in {"API_KEY": "test-key", "RAW_BUCKET": "test-raw",
                       "CASES_TABLE": "test-cases", "DOCS_TABLE": "test-docs",
                       "AUDIT_TABLE_NAME": ""}.items():
        monkeypatch.setenv(key, value)
    resource, cases, docs, s3 = (MagicMock() for _ in range(4))
    resource.Table.side_effect = lambda name: cases if name == "test-cases" else docs
    cases.get_item.return_value = {"Item": {"case_id": "case-test"}}
    docs.get_item.return_value = {}
    docs.name = "test-docs"
    monkeypatch.setattr(boto3, "resource", lambda *a, **kw: resource)
    monkeypatch.setattr(boto3, "client", lambda *a, **kw: s3)
    path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    spec = importlib.util.spec_from_file_location("intake_under_test", path)
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)
    monkeypatch.setattr(main, "now_iso", lambda: "2026-10-20T10:00:00Z")
    calls, order = [], []
    s3.upload_fileobj.side_effect = lambda *a, **kw: order.append("s3")
    resource.meta.client.transact_write_items.side_effect = lambda **kw: order.append("commit")

    class Recorder:
        def file_received(self, **values):
            order.append("audit")
            calls.append(values)

    main.app.state.audit_listener = Recorder()
    with TestClient(main.app) as client:
        response = client.post(
            "/v1/cases/case-test/documents", headers={"x-api-key": "test-key"},
            files=[("files", ("a.pdf", b"%PDF-1.4\nsynthetic", "application/pdf"))],
        )
    assert response.status_code == 201
    row = resource.meta.client.transact_write_items.call_args.kwargs["TransactItems"][0]["Put"]["Item"]
    assert calls == [{"case_id": row["case_id"], "document_id": row["document_id"],
                      "occurred_at": row["received_at"]}]
    assert order == ["s3", "commit", "audit"]
```

| Test | RED | GREEN |
|---|---|---|
| `test_new_upload_emits_once_after_commit` (skeleton) | HTTP 201, ale `calls == []`, chybí audit po commitu. | Jeden call s potvrzenými ID/časem, pořadí S3→commit→audit. |
| Duplicate a concurrent loser (rozšířit fixture) | Regresní guard; samostatně nemusí být RED. | Žádný další event, winner row beze změny. |
| Smíšená souběžná výhra + vlastní commit | Chybí event pro vlastní nový řádek. | Event jen pro vlastní úspěšnou transakci. |
| Failed metadata commit / S3 error | Regresní guard; samostatně nemusí být RED. | Stejná chyba a žádný event. |
| NoOp / funkční / failing sink caller parity | Nový listener před implementací chybí; zachytit až po základním caller RED. | Stejné business efekty i návrat/chyby; audit chyba nepropaguje. |

- Ve `test_audit_listener.py` doplnit identity assertion pro stejné case/document při jiném čase; zkontrolovat sedmipolový allowlist bez run_id/obsahu. Pro chyby factory/serializace/sinku požadovat návrat bez výjimky a nejvýše jeden pokus, bez chaos matice.

## Testing
- Připravit izolované Python prostředí s intake requirements, pytest/httpx a interním package; nepovažovat chybu importu/dependency za RED. Pro processing regresi použít její plné existující test dependencies v kompatibilním prostředí; neslučovat konfliktní piny s intake runtime.
- Spustit focused GREEN: `PYTHONPATH=be-document-processing/src python3 -m pytest -q be-intake/tests/test_monitor_file_received.py be-intake/tests/test_audit_listener.py`.
- Spustit stávající processing regresi v jejím prostředí: `python3 -m pytest -q` s workdir `be-document-processing`; uchovat původní audit storage testy a výsledky.
- Zachovat přesný registrovaný gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`; neúspěch zaznamenat jako konkrétní blocker/follow-up.
- Offline validovat změněnou šablonu: `cfn-lint be-intake/template.yaml`; ověřit diff audit ARN a nezměněné business schéma/oprávnění.
- Vybudovat skutečný runtime image z kořene: `docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:filereceived-local .`; zaznamenat `docker image inspect wonderfulkb-ingest:filereceived-local --format '{{.Id}}'`.
- Spustit bez bind mountu a bez PYTHONPATH: `docker run --rm --network none --entrypoint python wonderfulkb-ingest:filereceived-local -c 'import importlib.metadata as m; import document_processing.audit.audit_listener as a; from document_processing.audit.audit_storage import AuditStore; print(m.version("wonderfulkb-document-processing")); print(a.__file__); assert "/site-packages/" in a.__file__'`. Vyžadovat úspěšný import instalované distribuce, nikoli source checkoutu.
- Ověřit také import `main:app` v témže image s pouze syntetickými env `API_KEY`, `RAW_BUCKET`, `AWS_DEFAULT_REGION=eu-central-1`, `AWS_EC2_METADATA_DISABLED=true`, prázdným `AUDIT_TABLE_NAME` a vypnutou sítí; nesmí se načíst worker ani těžké processing dependencies.
- Prověřit směr importů: caller závisí pouze na malém listener rozhraní, composition root na factory; audit package neimportuje intake/business, hlavní upload nevytváří event/storage DTO ani audit catch/retry. Zachovat existující auth/API kontrakt.
- Při dokončení implementace použít `skill:validate-implementation` a jako poslední krok `skill:save-learning`; lokální test/build důkaz předat odděleně od budoucího deployed smoke.
