# Plan 2026-10-20: Monitoring runtime producer/context

Rozhodnout implementační větev podle doloženého canonical calleru a schváleného execution-owner rozhraní. Aktuální důkazy ukazují blocker; bez nového autoritativního kontraktu se zdrojová integrace neimplementuje ani nevydává za dokončenou.

## Analysis

- `plans/monitoring/runtime-producer-context-contract.md` a host review `plans/checkpoints/task-626722a4-f9fd-46a9-8304-17b9f24de1cc.host-review.md` dokládají chybějící canonical build provenance, stabilní logical-run identity, confirmed/ambiguous enqueue result i atomický claim+attempt.
- Trigger caller dnes zahazuje SQS send response; claim vrací status bez attempt ordinalu; worker předává do `run_document` pouze case/document IDs a warm-cached `Options`.
- Pokud execution owner mezitím neposkytne schválené rozhraní včetně crash/lease/concurrency sémantiky, zachovat blocker kontrakt a vyžádat přesné rozhodnutí. Nevymýšlet counter, outbox, fencing, runtime schema ani fake identity; nepoužít test double jako důkaz integrace.
- Zachovat izolaci auditu: business caller předává pouze minimální hodnoty přes injektovaný listener port; event konstrukce, serializace, I/O a fail-open izolace náleží audit modulu.
- Relevant learning: `learnings/architecture/2026-10-20_attemptstarted-audit-contract-preserves-producer-identity.md` — attempt identitu dodává producer; receive count ani audit data ji nenahrazují.

## Approach

1. Znovu ověřit pouze vlastněné trigger/build/caller source a existující kontrakt; přijmout interface jen při doloženém canonical build calleru a explicitním schválení stabilní logical-run identity, typed enqueue outcome, atomického claim+attempt a immutable context forwarding.
2. Při absenci kterékoliv části skončit přesným execution-owner rozhodovacím vstupem v `plans/monitoring/runtime-producer-context-contract.md`; žádná source změna ani tvrzení o hotové integraci.
3. Teprve po existenci kompatibilního rozhraní připojit minimální immutable scalar context přes skutečné enqueue/claim hranice do `run_document/Options` a listeneru, bez změny retry/DLQ/lease/business semantics.
4. Pro skutečného calleru ověřit NoOp/functional/failing sink ekvivalenci: writes/pořadí, návraty, exceptions a provider call count.

## Implementation

- Nejprve ověřit projektový Python interpreter `be-document-processing/.venv/bin/python` a dependency imports; žádný system Python fallback.
- Jestli interface chybí, aktualizovat pouze přesný blocker decision/contract; nevyrábět TDD RED/GREEN ani synthetic producer.
- Jestli interface existuje, vytvořit vlastní focused tests nejprve, provést genuine RED/GREEN se stejným argv a proof pod novým task ID; následně implementovat pouze vlastněné `be-validator-agent` caller/context seam a focused tests.
- Po integraci spustit relevantní package pytest s canonical cwd/PYTHONPATH, focused caller/store/sink testy a registrovaný backoffice test/build gate.

## Testing

- Interpreter/dependency preflight: `be-document-processing/.venv/bin/python -c 'import pytest'` z rootu; pro validator suite použít canonical package cwd/PYTHONPATH, aby `backfill` import fungoval.
- Relevantní validator tests: `tests/test_enqueue.py`, `tests/test_worker.py`, `tests/test_end_to_end.py`; AWS závislosti pouze Moto/fixtures.
- Audit package: focused caller/store/sink tests a relevantní pytest suite; root-level collection error není product RED ani GREEN.
- Registry gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- Žádné live/replay/provider/inference/deploy/scheduler/lifecycle ani source jiných projektů.

## TDD: skip

Aktuálně doložený execution-owner interface chybí, takže testovatelný source behavior ani genuine RED nelze vymezit bez spekulativní změny execution semantics. Po dodání skutečného schváleného rozhraní implementační řez musí začít TDD cyklem dle skill:tdd.

## Files

| Cesta | Podmíněná změna |
|---|---|
| `plans/monitoring/runtime-producer-context-contract.md` | Pouze doplnit přesné nové owner rozhodnutí, pokud interface stále chybí. |
| `be-validator-agent/trigger/common.py`, `worker_handler.py`, `pipeline/run.py` | Pouze po schváleném kompatibilním interface; minimální producer/context forwarding. |
| `be-validator-agent/trigger/tests/test_enqueue.py`, `test_worker.py`, `test_end_to_end.py` | Caller differential/concurrency testy pouze po skutečném interface. |
| `be-document-processing/tests/` | Pouze relevantní focused listener/sink differential coverage, pokud jde o vlastněný integrační seam. |

## Progress

- [x] Načten dosavadní blocker kontrakt a host review.
- [x] Zjištěn relevantní audit identity learning.
- [ ] Znovu ověřit skutečný canonical seam a rozhodnout blocker vs. schválená integrace.
- [ ] Provést odpovídající contract-only dokončení nebo TDD implementaci a gates.
