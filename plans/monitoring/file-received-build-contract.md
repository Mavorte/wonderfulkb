# FileReceived: intake build a interní audit kontrakt

Lokálně ověřeno pro `task-9681bd1b-c317-4f89-ad43-e221f2d05cf6` dne 2026-10-20.

## Rozhraní a sémantická hranice

- Composition root: `main.app.state.audit_listener = audit_listener.from_env()`.
- `AuditListener.file_received(*, case_id: str, document_id: str, occurred_at: str) -> None`;
  implementace `FileReceivedAudit`, vypnutí `NoOpAudit` v interním `document_processing.audit`.
- Existující `store_and_commit` vrátí pouze `todo` úspěšné metadata transakce.
  Caller předá tři skaláry potvrzeného řádku, čas z jeho `received_at`.
  Pořadí S3 → metadata commit → audit; duplicate, concurrent loser a failed commit neemituje.
- `AuditStore.put(FileReceived) -> Literal["inserted", "duplicate", "disabled", "unavailable"]`.
  Listener izoluje konstrukci, validaci a sink; store izoluje serializaci a persistence.
  Žádný audit retry, outbox ani doplňování chybějící události při duplicate uploadu.
  Best-effort: výpadek může znamenat chybějící událost, business úspěch/chyba se nemění.

## Obálka a identita

Sedm polí: `schema_version=1`, `event_id`, `case_id`, `document_id`, `sequence=0`,
`type="FileReceived"`, `occurred_at`. Bez run ID, názvu, hashe nebo obsahu dokumentu.

`event_id = str(uuid5(uuid.NAMESPACE_URL, identity))`, kde `identity` je
`json.dumps(["wonderfulkb.audit.v1", "FileReceived", case_id, document_id], ensure_ascii=True, separators=(",", ":"))`.
Namespace URL UUID: `6ba7b811-9dad-11d1-80b4-00c04fd430c8`.
Identita nezávisí na čase ani sequence. Store přidá technické klíče:
`pk = json.dumps([case_id, document_id], ensure_ascii=True, separators=(",", ":"))`,
`sk = "EVENT#" + event_id`; conditional put nepřepisuje původní událost.

## Konfigurace a IAM

`AUDIT_TABLE_NAME` (prázdné/nenastavené = NoOp), SDK region `eu-central-1`,
connect/read timeout 1/2 s, `retries={"total_max_attempts": 1}`.
`be-intake/template.yaml` parametr `AuditTableName` defaultuje na
`wonderfulkb-uw-document-processing-audit`; PutItem/Query jsou omezené na ARN této tabulky.
Existující tabulku vlastní `be-intake/documents-table/template.yaml`; žádná druhá tabulka
ani změna business schématu. Intake šablona nedefinuje App Runner service/env:
při budoucím nasazení explicitně namapovat `AUDIT_TABLE_NAME` na stejný název jako
`AuditTableName` a skutečně vytvořenou audit tabulku. Toto není důkaz runtime konfigurace.

## Přesný build a import výsledného artefaktu

Spouštět z kořene repa. Builder vytvoří wheel ze skutečného `pyproject.toml` a `src`,
runtime jej non-editable nainstaluje přes `pip install --no-deps`. Celé worker dependencies
neinstaluje (jejich piny se liší); audit používá existující intake boto3/botocore.
Žádné kopírování audit zdroje do `/app`. Runtime zůstává UID 10001, port 8080, uvicorn CMD.

```bash
docker build --platform linux/amd64 -f be-intake/app/Dockerfile -t wonderfulkb-ingest:filereceived-local .
docker image inspect wonderfulkb-ingest:filereceived-local --format '{{.Id}}'
docker run --rm --network none --entrypoint python wonderfulkb-ingest:filereceived-local -c 'import importlib.metadata as m; import document_processing.audit.audit_listener as a; from document_processing.audit.audit_storage import AuditStore; print(m.version("wonderfulkb-document-processing")); print(a.__file__); assert "/site-packages/" in a.__file__'
docker run --rm --network none --entrypoint python -e API_KEY=synthetic-key -e RAW_BUCKET=synthetic-raw -e AWS_DEFAULT_REGION=eu-central-1 -e AWS_EC2_METADATA_DISABLED=true -e AUDIT_TABLE_NAME= wonderfulkb-ingest:filereceived-local -c 'import sys; import main; from document_processing.audit.audit_listener import NoOpAudit; assert isinstance(main.app.state.audit_listener, NoOpAudit); assert "document_processing.worker" not in sys.modules; assert "pymupdf" not in sys.modules; print(main.app.title)'
```

Výsledný image ID: `sha256:b52b2b7bb468bb2562f3bf2c44682b6f98b101a21eee395bb529a78b56676667`.
Build exit 0; oba importy exit 0 bez bind mount/PYTHONPATH, se sítí vypnutou a runtime userem.
Výstup: `1.0.0`, `/usr/local/lib/python3.12/site-packages/document_processing/audit/audit_listener.py`,
`wonderfulkb-ingest`. AMD64 image běžel na ARM64 hostu emulovaně (Docker platform warning).

Historie: první image `sha256:f10f2139f44573f333c0d37f6c1b53f0b0fa0ad42bd1e1b91f890e30931efff5`
prošel package importem, ale `main` import selhal `PermissionError: /app/main.py`.
Oprava `COPY --chmod=644` odstraňuje závislost na host source módu; výše uvedené výsledky
patří novému image. Původní neúspěch není považovaný za PASS.

## Lokální ověření

- TDD helper přijal skutečné RED (201/S3/commit, chybějící listener call) a GREEN stejným argv:
  `env PYTHONPATH=be-document-processing/src /Users/michal/.openclaw/tmp/opencode/filereceived-py312/bin/python -m pytest -q be-intake/tests/test_monitor_file_received.py -k new_upload`.
  Kanonický důkaz: `plans/checkpoints/task-9681bd1b-c317-4f89-ad43-e221f2d05cf6.red-green-proof.md`.
- Caller/listener: `PYTHONPATH=be-document-processing/src /Users/michal/.openclaw/tmp/opencode/filereceived-py312/bin/python -m pytest -q be-intake/tests/test_monitor_file_received.py be-intake/tests/test_audit_listener.py`.
  Výsledek: 16 passed (jedno upozornění Starlette/AnyIO).
  Differential scénáře zahrnují S3, metadata, cleanup i content-hash writes/pořadí s NoOp, fungujícím auditem a selhávajícím sinkem.
- Processing regrese: `.venv/bin/python3 -m pytest -q` v `be-document-processing`: 88 passed.
- Registrovaný gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`: 17 passed, build 5 functions.
- `/Users/michal/.openclaw/tmp/opencode/filereceived-py312/bin/cfn-lint be-intake/template.yaml`: exit 0.
- `git diff --check`: exit 0. Kontrola importů: intake závisí jen na listeneru/factory,
  audit neimportuje business/worker; hlavní tok nemá audit DTO, storage nebo audit catch/retry.

Pouze lokální build/test/import. AWS nasazení a live HTTP/DB nebyly součástí tohoto zadání ani provedeny.
