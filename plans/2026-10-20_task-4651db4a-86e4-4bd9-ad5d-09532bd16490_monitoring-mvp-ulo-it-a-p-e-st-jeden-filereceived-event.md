# Plan 2026-10-20: Monitoring MVP: uložit a přečíst jeden FileReceived event

## Progress
- [x] Získat kanonickou cestu plánu pro task-4651db4a-86e4-4bd9-ad5d-09532bd16490.
- [x] Prozkoumat kontrakt, testy, šablony a relevantní learnings.
- [x] Opravit invalid_header prefixem `# Plan 2026-10-20:`; před předáním ověřit kanonický artefakt a přesný seznam nadpisů.

## Analysis
- Řídit se `plans/monitoring/mvp-reference-20261019.md` § Minimum společné prvním taskům a `be-document-processing/PROCESSING-MONITOR-API.md` § Event a data / Bounded čtení.
- Zachovat tři existující testy v `be-document-processing/tests/test_monitor_audit_storage.py`; doplnit kontrolu skutečného Query limitu a zákazu Scan (současný test ověřuje pouze propagaci výjimky).
- Přidat interní audit package; `document_processing/__init__.py` a business `Settings` ponechat kompatibilní. Konfiguraci izolovat v audit storage.
- Vlastnictví zdrojů odvodit z `be-intake/documents-table/template.yaml` (tabulky) a `be-intake/template.yaml` (App Runner InstanceRole); starý SAM v document-processing není aktuální API cíl. Audit resource definovat jen jednou.
- Aplikovat learnings o úzkém audit scope a zachování TDD historie; recall backend `local`, collection `wonderfulkb-learnings`, diagnostic `Collection not found`. Historické problémy závislostí nepřenášet na hostem připravenou `.venv`.
- Pro opravu retry použít `km_tasks.task.artifacts.inspect_plan_artifact`: správné `##` sekce samy nestačí, první řádek musí začínat `# Plan`. Neměnit task markdown ani ručně přepisovat stav tasku.
- Z discovery použít `recall-knowledge` pro pravidla, `tdd` pro následnou implementaci a `validate-implementation` pro závěrečnou kontrolu; `save-learning` použít při dokončení plánování. Architekturu odvodit z MVP reference a existujících templates; pod `docs/` není PlantUML diagram.

## Approach
- Definovat frozen dataclass `FileReceived` přesně se sedmi poli `schema_version,event_id,case_id,document_id,sequence,type,occurred_at`; podporovat verzi 1 a typ FileReceived, neprázdná ID, nezápornou integer sequence a UTC occurred_at. Serializovat explicitním allowlistem; jediným uloženým timestampem zůstane occurred_at.
- Kódovat `pk` z jednoznačné kanonické JSON dvojice `[case_id,document_id]`; `sk = EVENT#<event_id>`. Identita je stabilní v document scope i při změně sequence/occurred_at. Uložit pouze obálku + technické pk/sk; sequence není allocator, čas ani součást identity. Číst ve stabilním technickém pořadí sk; neslibovat chronologickou timeline ani úplnost historie.
- Nabídnout `AuditStore(table)`, `put(event)` a `read_document(case_id,document_id,limit=50,next_token=None)`; page má `items` a `next_token`. Výsledek put rozlišuje `inserted`, `duplicate`, `disabled`, `unavailable`; `enabled` explicitně signalizuje konfiguraci. Čtení vypnutého store vyhodí `AuditNotConfigured`, dostupnostní chyby se propagují.
- Použít jediný `PutItem` s `attribute_not_exists(pk) AND attribute_not_exists(sk)`, bez přepisování/UpdateItem. ConditionalCheckFailed znamená duplicate; ostatní persistence chyby znamenají fail-open unavailable, bez retry smyčky či logování obsahu eventu.
- Každé čtení provede právě jeden `table.query` s `KeyConditionExpression` na pk, `Limit` 1–100 a případným `ExclusiveStartKey`; žádný Scan ani dočítání dalších stránek. Použít `ConsistentRead=True` pro bezprostřední put→read.
- V `audit_queries.py` zakódovat verzovaný opaque base64url JSON token s operation=`document_events`, case_id, document_id a LastEvaluatedKey. Omezit vstupní délku (např. 4096 znaků), validovat strukturu, scope i pk/sk před Query; cizí/malformed token odmítnout ValueError. Token není autorizační credential. Vázat pokračování na scope a operaci; refresh začíná bez tokenu.
- Konfiguraci držet v `AuditStore.from_env()`: prázdné `AUDIT_TABLE_NAME` vrátí explicitně vypnutý store bez AWS inicializace; jinak resource v eu-central-1 s `Config(connect_timeout=1,read_timeout=2,retries={"total_max_attempts":1})`. Konfigurovaný write initialization failure převést na unavailable, nikoli na disabled; read failure nesmí vrátit prázdnou page.

## Implementation
1. Použít `skill:tdd` a `skill:recall-knowledge`; pro následné boto3 změny načíst `skill:aws-sdk-python-usage`, pro resource/IAM `skill:aws-cloudformation` a `skill:aws-iam`. Z discovery použít také `skill:validate-implementation` po implementaci a `skill:save-learning` při dokončení.
2. Nejdříve upravit pouze `tests/test_monitor_audit_storage.py` podle skeletonu; zachovat původní tři testy a fixture. Zachytit nový RED s aktuálním task ID a explicitním repository evidence rootem; zkontrolovat konkrétní testovou assertion, ne pouze exit code helperu.
3. Přidat `audit/__init__.py` pouze jako package marker, `audit_events.py`, `audit_storage.py`, `audit_queries.py` podle Approach. Neměnit root package API, bootstrap, service ani producenty.
4. Přidat do `be-intake/documents-table/template.yaml` jediný `AuditTable` s TableName `wonderfulkb-uw-document-processing-audit`, pk/sk String, PAY_PER_REQUEST, šifrováním a Retain pro deletion/replacement. Bez TTL, GSI a business-table diffu; vystavit audit table name/ARN v Outputs.
5. V `be-intake/template.yaml` rozšířit stávající InstanceRole jedním statementem pouze `dynamodb:PutItem` a `dynamodb:Query` na přesné audit table ARN odvozené z AWS partition/region/account. Nedávat audit CRUD wildcard ani měnit SAM API/worker role. `.env.example` doplnit `AUDIT_TABLE_NAME=` s vysvětlením disabled a časových limitů; runtime App Runner konfiguraci řeší navazující slice.
6. Zachytit GREEN stejným focused argv, zkontrolovat výstup i canonical proof; spustit registrovaný gate. Ověřit diff podle Files a uchovat historické důkazy včetně neúspěchů. Aktuální task je interní store bez HTTP, hooku, run projekcí, revision/fencing, incremental refresh, TTL a deploymentu.

## TDD
- Implementace TDD cyklu dle skill:tdd. Editovat existující `be-document-processing/tests/test_monitor_audit_storage.py`, nepřepisovat jeho původní scénáře. Framework: pytest + existující Moto fixture a monkeypatch.
- Nahradit pouze dva audit importy následujícím guardem a přidat testy níže. Guard převádí očekávanou absenci cílového API na nasbíranou contract assertion; chyby jiných dependencies dál propaguje. Nezavádět produkční stub pro výrobu RED.

```python
# Náhrada audit importů; pytest/Moto/boto3 importy a fixture zůstávají.
try:
    from document_processing.audit.audit_events import FileReceived
    from document_processing.audit.audit_storage import AuditStore
except ModuleNotFoundError as exc:
    if not (exc.name == "document_processing.audit" or
            exc.name.startswith("document_processing.audit.")):
        raise
    FileReceived = AuditStore = None


def test_audit_api_contract_exists():
    assert callable(FileReceived), "Missing FileReceived audit contract"
    assert callable(AuditStore), "Missing AuditStore implementation"


def test_duplicate_identity_does_not_depend_on_sequence(audit_table):
    assert callable(AuditStore), "Missing AuditStore implementation"
    store = AuditStore(audit_table)
    first = event()
    store.put(first)
    store.put(event(sequence=99))
    assert store.read_document("case-1", "doc-1", limit=10).items == [first]


def test_successful_read_is_one_bounded_query(audit_table, monkeypatch):
    assert callable(AuditStore), "Missing AuditStore implementation"
    store = AuditStore(audit_table)
    store.put(event())
    calls = []
    original = audit_table.query

    def query(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    def forbidden_scan(*args, **kwargs):
        pytest.fail("Audit reads must not Scan")

    monkeypatch.setattr(audit_table, "query", query)
    monkeypatch.setattr(audit_table, "scan", forbidden_scan)
    page = store.read_document("case-1", "doc-1", limit=1)
    assert [item.event_id for item in page.items] == ["evt-1"]
    assert len(calls) == 1
    assert calls[0]["Limit"] == 1
    assert "KeyConditionExpression" in calls[0]
```

| Test/scénář | RED očekávání | GREEN očekávání |
|---|---|---|
| `test_audit_api_contract_exists` | Nasbíraný test selže na Missing FileReceived audit contract; ne conftest/import setup failure | Oba reálné konstruktory existují |
| `test_duplicate_identity_does_not_depend_on_sequence` | Chybějící AuditStore assertion; následně kontrolovat vlastní storage assertion | Změna sequence stejné identity ponechá jediný původní event |
| `test_successful_read_is_one_bounded_query` | Chybějící AuditStore assertion; následně kontrolovat skutečné Query chování | Jeden Query s limitem, bez Scan |
| Původní round-trip/duplicate test | Zachovat jako behaviorální specifikaci; před API mohou selhat na chybějícím konstruktoru | Shodná ID i celá obálka, změněný occurred_at nepřepíše první |
| Původní document scope/pagination test | Zachovat původní assertions | Dvě stránky doc-1, doc-2 odděleně, poslední token None |
| Původní read-error test | Zachovat původní assertions | RuntimeError se propaguje místo empty success |

- Přidat jen malé doplňky do stejného test souboru: cross-case/cross-document token odmítnout před Query; limit 0/101 odmítnout; vypnutý store nevolá AWS a read hlásí not configured; jeden simulovaný PutItem outage vrátí unavailable; resource factory obdrží konečné timeouty a jeden total attempt. Není potřeba plošná fault matice.
- Neprezentovat počáteční chybějící API jako důkaz selhání DynamoDB semantiky; doklad zkontrolovat na testovou contract assertion. Pokud conftest/dependency setup selže, uložit diagnostiku a vyřešit blocker před implementací; historické výsledky nepřepisovat.
- Spustit z cwd `/Users/michal/Projects/wonderfulkb/be-document-processing` přesný child argv `.venv/bin/python -m pytest -q tests/test_monitor_audit_storage.py` v obou fázích:

```bash
TASK_ID=task-4651db4a-86e4-4bd9-ad5d-09532bd16490 python3 /Users/michal/.config/opencode/skills/tdd/scripts/proof-capture.py red --project-root /Users/michal/Projects/wonderfulkb -- .venv/bin/python -m pytest -q tests/test_monitor_audit_storage.py
# Teprve po ověření RED implementovat; pak ze stejného cwd:
TASK_ID=task-4651db4a-86e4-4bd9-ad5d-09532bd16490 python3 /Users/michal/.config/opencode/skills/tdd/scripts/proof-capture.py green --project-root /Users/michal/Projects/wonderfulkb -- .venv/bin/python -m pytest -q tests/test_monitor_audit_storage.py
```

- Ověřit helper `accepted_red` / `accepted_green`, konkrétní testový výstup a `plans/checkpoints/task-4651db4a-86e4-4bd9-ad5d-09532bd16490.red-green-proof.md`. Žádné kopírování starších task proofů ani ruční editace evidence.

## Testing
- Po focused GREEN spustit z repository root registrovaný gate přesně: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` (timeout 300 s); případný pre-existing failure uvést konkrétně.
- Staticky zkontrolovat template diff: jedna audit resource, shodné pk/sk s Moto fixture, IAM jen audit ARN, žádný TTL/business diff; nepovažovat lokální testy za důkaz deploymentu.
- Ověřit uložený item allowlistem sedmi polí + pk/sk, token scope a jedno Query na stránku. Neodvozovat HTTP observed_at ani business existenci z audit store.

## Files
| Cesta | Konkrétní změna |
|---|---|
| `be-document-processing/src/document_processing/audit/__init__.py` | Nový package marker bez změny root API |
| `be-document-processing/src/document_processing/audit/audit_events.py` | FileReceived dataclass, validace a explicitní serializace |
| `be-document-processing/src/document_processing/audit/audit_storage.py` | Conditional put, fail-open status, config/resource factory, bounded read delegace |
| `be-document-processing/src/document_processing/audit/audit_queries.py` | Page, klíče, token encode/decode, jeden document Query |
| `be-document-processing/tests/test_monitor_audit_storage.py` | Zachovat původní testy; doplnit skeleton a cílené chybějící assertions |
| `be-document-processing/.env.example` | Volitelný AUDIT_TABLE_NAME, disabled/timeout dokumentace |
| `be-intake/documents-table/template.yaml` | Jediná auditní tabulka a Outputs |
| `be-intake/template.yaml` | Přesné PutItem/Query oprávnění stávající instance role |
