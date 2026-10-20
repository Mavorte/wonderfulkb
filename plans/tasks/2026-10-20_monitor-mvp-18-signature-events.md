---
title: "Monitoring MVP: události skutečné detekce podpisů"
type: implementation
---
# Monitoring MVP: události skutečné detekce podpisů

## Goal
Rozšířit Step kontrakt/store o signature_detection bez podpisových hodnot a bez změny OCR statusu. Event/store část proposal `proposal-20261019-150954-c8891f`, `slice-signatures`.

## Files/functions
Existující audit package `be-document-processing/src/document_processing/audit/`: `audit_events.py`, `audit_storage.py` a fail-open hranice podle potřeby; focused `be-document-processing/tests/test_monitor_signature_events.py`. Rozhraní Step z `plans/tasks/2026-10-20_monitor-mvp-10-source-validation-events.md`. Sémantické reference pouze read-only `pipeline.py:114–115`, `signatures.py:153–163`, ne důkaz deployed workeru.

## Change
- Stávající StepStarted/StepFinished/StepFailed, stage=signature_detection; předaný run_id a kladný attempt_no, bez page_number. Producer dodává stabilní event_id, audit žádnou execution identitu negeneruje. Žádný nový event typ.
- Start jen skutečně zapnutý a spuštěný detector; disabled nevyrábí start/skipped/success. StepFinished pouze skutečně returned status=completed, i s nulou nálezů. Returned status=failed je StepFailed i když detect nevyhodí výjimku; zachycená raised chyba také failure. Neznámý/chybějící konec unknown, ne domyšlený success. Kontrakt sám detector nevolá ani neodvozuje výsledek z OCR statusu.
- Pouze skutečně měřené finite nezáporné duration_ms na terminálu a bezpečný error_code na failure. Žádné podpisy/citace/geometry/nálezy/counts, raw provider errors, S3 klíče, konfigurace či business Page/SignatureSection. Historickou signature konfiguraci nedoplňovat z dnešního environmentu. Žádná změna OCR processing statusu.
- Conditional event_id idempotence, document partition/occurred_at a fail-open tvorba/validace/serializace/persistence zachovány. Doložený terminal-only fragment je přípustný i bez úvodních RunQueued/AttemptStarted/StepStarted.

## Boundaries
Pouze wonderfulkb; žádný producer hook, cloud/model call/deploy, business/queue/retry/lease/execution změna, nový store/index/projekce nebo detekční logika. Tato část není live signature slice. Nové soubory doménově kvalifikované, ne events.py/state.py/utils.py.

## Verification
Implement the TDD cycle using skill:tdd. Focused fake/Moto: completed a failed roundtrip, terminal-only, idempotence, run/attempt izolace, invalid scope/duration/business payload bez mutation. Synteticky reprezentovat returned-failed, raised-failed, completed-empty a disabled bez automatických observations; netvrdit reálné spuštění detectoru. NoOp/failing audit boundary nemění caller výsledek. Předchozí eventy a registrované gates zachovat; žádné AWS/inference.
