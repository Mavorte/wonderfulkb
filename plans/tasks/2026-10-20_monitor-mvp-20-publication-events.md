---
title: "Monitoring MVP: události potvrzené publikace výsledku"
type: implementation
---
# Monitoring MVP: události potvrzené publikace výsledku

## Goal
Event/store část `slice-result-published`, proposal `proposal-20261019-150954-c8891f`. Rozšířit Step stage=result_publishing a přijmout explicitní ResultPublished, bez kopie výsledku.

## Files/functions
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`, fail-open boundary podle potřeby; focused `be-document-processing/tests/test_monitor_publication_events.py`. Step kontrakt z `2026-10-20_monitor-mvp-10-source-validation-events.md`, sémantická reference `pipeline.py:125–130` (není live producer proof).

## Change
- StepStarted/StepFinished/StepFailed stage=result_publishing, run_id a kladný attempt_no, bez page_number. Step terminal jen měřené finite >=0 duration_ms, bezpečný failure error_code. ResultPublished stejný skutečný run/attempt scope a `result_status` completed/partial/failed podle skutečně publikovaného business výsledku, ne statusu runu. Producer-supplied stabilní event_id pro každý odlišný event, nezaměnit StepFinished a ResultPublished identitu.
- ResultPublished znamená všechny skutečně dokončené kroky validace+S3+owned job update+document update, ne S3-only nebo začátek zápisu. Partial publikace není automaticky RunFinished. Store pouze přijímá výslovné observations; business stav nečte, publikaci sám neprovádí ani neověřuje zpětným lookupem.
- Známé opaque artifact_ids/reference jen pokud skutečně existují; nevyžadovat smyšlenou immutable verzi/available reference. Bez dokumentového obsahu, business result/errors, bucket/key/URL nebo dnešní konfigurace. Reference nedokazuje historickou reprodukovatelnost; content resolver/download není scope.
- Ukládat idempotentně event_id ve stávajícím document logu, occurred_at jediný uložený event timestamp. Pozorovaný terminal/ResultPublished bez úvodního StepStarted/AttemptStarted/RunQueued je platný fragment; žádné syntetické doplnění začátku. Fail-open validace/serializace/write nesmí ovlivnit publish/retry nebo původní chybu.

## Boundaries
Pouze wonderfulkb. Bez producer hooku, změny pořadí/atomicity business writes/rollback/fencing, publish operace, model/AWS calls/deploy, queue/lease/retry/execution změny, outbox nebo stored projekce/index. Nepředstírat, že starý pipeline.py je deployed worker. Nové moduly doménové, ne events.py/state.py/utils.py.

## Verification
Implement the TDD cycle using skill:tdd. Focused fake/Moto: completed/partial/failed publikovaný outcome roundtrip, StepFailed bez ResultPublished pro nepozorovanou publikaci, terminal-only fragment, duplicate, run/attempt oddělení; invalid status/scope/page/duration/raw result odmítnuty bez mutation. Assert ResultPublished nevyrábí RunFinished ani business writes. NoOp/failing audit boundary ekvivalentní caller výsledek; předchozí eventy a registrované gates zachovat. Skutečné publish failure-point testy patří producer integration, ne falešnému store E2E.
