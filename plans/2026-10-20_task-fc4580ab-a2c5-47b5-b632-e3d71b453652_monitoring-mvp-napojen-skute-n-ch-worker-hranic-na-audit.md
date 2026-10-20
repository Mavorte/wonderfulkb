# Plan 2026-10-20: Monitoring MVP — audit skutečných worker hranic

Vymezit podporované worker stage podle checked-in callerů a připojit fail-open audit pouze tam, kde existuje skutečná potvrzená hranice a autoritativní immutable execution context.

## Analysis

- `be-validator-agent/pipeline/run.py` obsahuje skutečnou pipeline; `Options` je mutable a nemá execution identity. Page/cache/vision jsou v `transcribe_scans`; extraction, signatures i publish vyžadují callerově doloženou hranici.
- `plans/monitoring/runtime-producer-context-contract.md` zaznamenává blocker identity/context: trigger claim nedodává stabilní `run_id` ani `attempt_no`; `run_document` nedostává immutable per-execution context. SQS enqueue výsledek není rozlišený na potvrzený/ambiguous.
- `be-document-processing/src/document_processing/audit/` má event kontrakty a `audit_listener.py` s fail-open NoOp/store patternem. Ověřit, zda rozhraní podporuje požadované stage/payloady; nerozšiřovat auditní odpovědnost do pipeline.
- Proposal `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md`, zejména `Izolace implementace`, určuje jedno injected listener rozhraní, auditní logiku uvnitř package a krátký timeout bez retry.
- `plans/monitoring/next-slices-source-seams-20261019.md` a proposal jsou sémantickou referencí, nikoli důkazem deployed ownera. Starý `be-document-processing/.../pipeline.py`/signatures nejsou actual-owner evidence.
- Relevantní pravidlo: lifecycle eventy vyžadují producer-supplied autoritativní identity; nikdy neodvozovat attempt z receive count, audit řádků ani timestampů. Zdroje: `learnings/architecture/2026-10-20_audit-lifecycle-facts-without-invented-runtime-evidence.md`, `.../2026-10-20_attemptstarted-audit-contract-preserves-producer-identity.md`.

## Approach

1. Zmapovat actual entrypoint → queue/claim → pipeline callers, package import/install/build a testy. Vést seznam každé schválené stage jako supported pouze s callerem, eventem, payloadem a testem; ostatní označit unsupported s konkrétním chybějícím seam/context/build důvodem.
2. Nejprve vyřešit execution-context/build kontrakt bez změny identity, claim/lease/retry či queue semantics. Pokud chybí owner-approved immutable context nebo canonical build integration, nepřidávat producenty na tyto hranice a zapsat přesný blocker; žádné fake/no-op producer, globals ani alternativní execution model.
3. Pro doložené stage předat explicitní minimální hodnoty jedinému listeneru na skutečně potvrzených hranicích. Event creation, validation, serialization, timeout a izolace sink chyb zůstanou v `document_processing/audit/`; composition root provede injection.
4. Zachovat business writes, jejich pořadí/výjimky, provider-call count, retry/claim/publish chování. Neúplné či neznámé konce zůstanou unknown; capability se nikdy neodvozuje zpětně z aktuálního prostředí.

## Implementation

- Rozšířit auditní listener/event typy pouze pro stage, jejichž event/payload i skutečný source seam jsou podporované; doplnit bounded timeout a NoOp/failing-sink ekvivalenci v audit package.
- Při dostupném autoritativním contextu instrumentovat: source validation jako jediný start+finish/failure; novou page práci start + jediný PageCompleted/PageFailed; cache hit až po úspěšné validaci; extraction jen pro skutečný neprázdný completed vstup; enabled signature detector s rozlišením completed/returned-failed/raised-failed; publish po celé potvrzené publish hranici; retry po confirmed enqueue; terminal eventy jen při známém skutečném konci.
- Nepovažovat pre-call budget za vision call; cache metadata označit cached; returned empty extraction není failure; signature outcome nemění OCR status; S3-only/partial writes nejsou publish completion; failed claim, lease loss, conflict či ticho nejsou terminal; max-attempt bez claimu nedostává AttemptStarted.
- Vytvořit `plans/monitoring/worker-instrumentation-contract.md` s actual symbol/caller/event/payload/test/build-inclusion mapou a unsupported seams/důvody. Zaznamenat, že source/hooks nejsou deployed worker→HTTP smoke.
- Nespouštět cloud/model/live message/service/deploy operace ani nezavádět nový worker/artifact. Zachovat jen stávající worker artifact/build.

## Testing

- Caller-level fakes: NoOp, working listener, throwing sink; porovnat business writes/pořadí/návratové hodnoty/chyby a relevantní provider-call count.
- Pokrýt cache completed/failed/corrupt miss; native/vision/pre-call-budget; extractor success/error/empty input; signature returned/raised/disabled; publish failure points; retry confirmed/failed a max-attempt; stale-owner pouze pokud canonical semantics existují.
- Ověřit hermetický import/build audit package ze skutečného worker entrypointu a registered gate `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- Pokud required producer context/build seam chybí, testy/documentace musí tento blokátor uvést; syntetické testy nejsou důkazem supported actual branch ani deployed behavior.

## TDD

**Test file:** `be-validator-agent/pipeline/tests/test_pipeline.py` (rozšířit testy actual caller; audit-package unit tests umístit vedle odpovídajících testů v package)
**Framework:** pytest — stávající pipeline test suite.
**Run command:** `python -m pytest be-validator-agent/pipeline/tests/test_pipeline.py -q`
**Edit hint:** Append actual-caller differential tests; neizolovat samotný helper jako náhradu caller evidence.

```python
from pipeline.run import Options, run_document


def test_actual_worker_boundary_is_audited_without_changing_business_result(actual_worker, audit_spy):
    result = actual_worker.run(options=Options(aws=actual_worker.aws, audit=audit_spy))
    assert audit_spy.events == actual_worker.expected_confirmed_boundary_events  # RED until caller forwards context and invokes listener
    assert result == actual_worker.no_audit_result
```

| Test | RED | GREEN |
|---|---|---|
| `test_actual_worker_boundary_is_audited_without_changing_business_result` | Actual caller emits no event / lacks context | Supported boundary emits exactly documented event; result and writes match NoOp |
| failing sink differential at supported caller | Sink failure alters result or write/call behavior | Business behavior matches NoOp exactly |

Implementace TDD cyklu dle skill:tdd. Context/build blockers se nesmějí obcházet kvůli dosažení GREEN; testování probíhá jen pro doložené seams.

## Files

| Path | Planned change |
|---|---|
| `be-validator-agent/pipeline/run.py` | Minimální explicit context/listener forwarding a instrumentation pouze na doložených hranicích. |
| `be-validator-agent/trigger/worker_handler.py` and actual build/composition root | Forwardovat jen již existující autoritativní context; jinak zapsat blocker, neměnit claim/identity. |
| `be-document-processing/src/document_processing/audit/` | Event/listener implementation, fail-open timeout a package-owned serialization/error isolation. |
| `be-validator-agent/pipeline/tests/test_pipeline.py` plus audit package tests | Actual-caller differential and boundary tests. |
| `plans/monitoring/worker-instrumentation-contract.md` | Evidence-backed supported/unsupported capability a build/test map. |

## Progress

- [x] Načteny source/context contracts a izolace auditu.
- [ ] Ověřit přesný canonical caller/build seam a autoritativní context při implementaci.
- [ ] Implementovat pouze podporované hranice test-first, případné blockery přesně zdokumentovat.
- [ ] Spustit cílené tests, hermetic worker import/build a registered gates.
