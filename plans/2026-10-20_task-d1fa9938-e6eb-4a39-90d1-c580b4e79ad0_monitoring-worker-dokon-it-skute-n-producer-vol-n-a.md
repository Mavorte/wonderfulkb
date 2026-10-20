# Plan 2026-10-20: Monitoring worker — skutečná producer volání

Napojit doložitelné worker caller hranice na existující fail-open audit package a ověřit behaviorální ekvivalenci, bez změny execution identity/modelu.

## Progress

- [x] Zkontrolovat execution-context, caller a audit package kontrakty
- [x] Načíst související learnings a určit TDD požadavky
- [x] Zapsat plán; implementation remains pending

## Analysis

- `plans/monitoring/runtime-producer-context-contract.md` a aktuální `be-validator-agent/trigger/common.py` / `worker_handler.py` stále popisují claim vracející status string, enqueue zahazující response a `process_document` bez immutable attempt context. V `pipeline/run.py` chybí execution context i listener; současný `build.sh` nestage audit package.
- Přestože předchozí `worker-instrumentation-contract.md` označuje vše unsupported, musí být při implementaci znovu zmapovány konkrétní současné skutečné callery a dostupné identity. Chybějící context/producer/build cesta je explicitní blocker; nesmí se nahradit odvozenou identitou ani novým execution modelem.
- Auditní listener dnes definuje pouze `file_received`; rozsah rozhraní, timeout a fail-open izolace nových eventů musí zůstat v `be-document-processing/src/document_processing/audit/`.
- Skutečný `pipeline.run_document` má doložitelné page/cache větve, signature helper a publish writes, ale publish obsahuje několik zápisů a nemá v této cestě potvrzený atomický celek. Stage bez skutečného canonical calleru zůstává unsupported.
- Learned rules: AttemptStarted vyžaduje producer-supplied stable `run_id` a kladné `attempt_no`; nesmí se odvozovat z receive count/timestamp/event count. Dataclass eventy mají sdílet jednoduchou obálku a nemít duplicitní definice.
- Python package deklaruje `requires-python >=3.10`; všechny test/build příkazy musí použít `be-document-processing/.venv/bin/python` s korektním cwd/PYTHONPATH. Ověřit pytest, pypdf a deklarované dependencies ještě před TDD proof capture; staré pypdf RED není nové behavioral RED.
- Reference: `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` („Izolace implementace“); `plans/monitoring/next-slices-source-seams-20261019.md`; staré `pipeline.py` a `signatures.py` v jiném package nejsou důkazem canonical ownera.
- Relevant skills: `recall-knowledge` před implementací, `tdd` pro tento behaviorální task, `validate-implementation` po změnách. Projektový gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.

## Approach

Nejdříve ověřit, že existuje skutečné schválené immutable execution context rozhraní a skutečný worker build/composition root, který jej předává. Bez toho zastavit producer implementaci a přesně zapsat nepodporované boundaries; žádné falešné GREEN ani změna execution semantics. Pokud rozhraní je dostupné, implementovat jen supported caller/event páry přes jediný injektovaný fail-open listener.

## Implementation

1. Ověřit projektové soubory/branch a execution-owner interface: enqueue outcome, successful claim attempt identity, explicit context forwarding, composition root a artifact inclusion. Zachovat původní failed checkpoint/proof beze změny; nový proof patří pouze novému task ID.
2. Sestavit actual symbol → caller → event/payload → evidence mapu. Rozlišit source validation, page/cache, extraction, enabled signature detection, complete confirmed publish, confirmed retry a známé terminal ends; stage bez skutečné cesty ponechat unsupported.
3. Ověřit prostředí designovaným `.venv/bin/python`, cwd, `PYTHONPATH`, pytest, pypdf a declared dependencies; nepoužít systémový Python 3.9.
4. S `skill:tdd` vytvořit focused actual-caller RED testy a zachytit nový proof přes task ID `task-d1fa9938-e6eb-4a39-90d1-c580b4e79ad0`; stejná argv pro RED/GREEN. Pak přidat pouze nutné listener API/události v audit package, caller injection a build inclusion.
5. Diff testy NoOp / functioning / failing sinku pro skutečné caller branches; ověřit neměnné business writes/order/return/errors/provider-call count. Neemitovat událost při neconfirmed boundary; zachovat cache, empty extraction, signature status a partial publish významy.
6. Aktualizovat `worker-instrumentation-contract.md` skutečnými supported/unsupported mapami, symboly, payloady, testy a build/import evidencí; ponechat rozsah source/build evidence odlišený od deployed/live evidence.
7. Spustit relevantní worker/audit tests, hermetic import/build z worker entrypointu a registrovaný project gate. Bez deploy, live/model volání, replay či service writes.

## Testing

- Focused caller tests musí ověřit skutečné call sites, nikoli grep Markdownu: source validation outcome; nové page work/cache validated hit/pre-call budget; extractor success/error/empty input; signature returned-failed/raised-failed/disabled; každý existující publish failure point; confirmed/failed enqueue a max-attempt bez nového claimu.
- Differential runs pro NoOp, functioning a failing sink porovnají business write sekvenci, výsledný návrat/chybu a relevantní počet provider calls.
- Hermetický build/import dokládá, že worker artifact skutečně obsahuje a importuje audit package; nepovažovat to za deployed smoke.
- Před proof capture zaznamenat test dependency availability. Zachovat staré failed/inconclusive důkazy bez přeznačení.
- Spustit `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` jako registrovaný gate.

## TDD

**Workflow:** implementace cyklu dle `skill:tdd`; nejprve focused RED, následně GREEN se stejnou argv a důkazem v `plans/checkpoints/task-d1fa9938-e6eb-4a39-90d1-c580b4e79ad0.red-green-proof.md`. Při nedostupném skutečném identity interface zaznamenat blokující RED/unknown poctivě; nevyrobit production fake identity.

**Test file:** `be-validator-agent/trigger/tests/test_audit_instrumentation.py`  
**Framework:** pytest (skutečný worker caller má pytest tests).  
**Run command:** `be-document-processing/.venv/bin/python -m pytest be-validator-agent/trigger/tests/test_audit_instrumentation.py -q`  
**Edit hint:** nový test soubor; použít package import pattern `from trigger import worker_handler`; rozšířit existující worker fake fixture v `test_worker.py` až po ověření skutečného composition interface.

```python
import inspect

from trigger import worker_handler


def test_process_document_accepts_explicit_execution_context():
    parameters = inspect.signature(worker_handler.process_document).parameters
    assert "execution_context" in parameters  # RED: current caller has no authoritative context parameter
```

| Test | RED | GREEN |
|---|---|---|
| successful claim forwards owner context and calls producer | caller lacks context and producer invocation | exact owner-supplied context arrives at real caller and one event is observed |
| failed claim emits no start | no authoritative claim outcome/context | no producer call or event; existing return unchanged |
| sink failure equivalence | no injected fail-open audit boundary at actual caller | same business writes/order/result/error/provider count as NoOp |

## Files

| Path | Planned change |
|---|---|
| `be-document-processing/src/document_processing/audit/` | Extend the existing injected listener/event boundary only for supported producer facts; isolate validation, serialization and sink failures here. |
| `be-validator-agent/trigger/worker_handler.py`, `be-validator-agent/pipeline/run.py`, actual caller/build files | Pass only existing authoritative context and inject listener if supported interface/build owner exists; never alter claim, lease, retry or business order. |
| `be-validator-agent/trigger/tests/test_audit_instrumentation.py` and focused pipeline tests | Actual-caller differential and behavior tests with NoOp/functioning/failing listener. |
| `be-validator-agent/trigger/build.sh` and dependency manifest (only if canonical artifact requires it) | Include existing audit package/dependencies in the worker artifact; no new service. |
| `plans/monitoring/worker-instrumentation-contract.md` | Replace unsupported statements only with source-backed caller/event/test/build evidence; retain unsupported rows and evidence boundaries. |
