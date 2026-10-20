---
title: "Monitoring MVP: události skutečně provedené extrakce"
type: implementation
---
# Monitoring MVP: události skutečně provedené extrakce

## Goal
Existující Step event/store kontrakt přijme začátek a pozorovaný úspěch/selhání kroku extraction, bez ukládání vytěžených hodnot a bez nového typu události. Malá event/store část slice 7.

## Files/functions
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`, existující auditní fail-open hranice podle potřeby; focused `be-document-processing/tests/test_monitor_extraction_events.py`. Proposal `proposal-20261019-150954-c8891f`, sections `slice-extraction`, `instrumentation`; Step allowlist v `plans/tasks/2026-10-20_monitor-mvp-10-source-validation-events.md`. Sémantická reference pouze read-only: `be-document-processing/src/document_processing/pipeline.py:104–111`, `extraction.py:LocalExtractor.extract`.

## Change / exact contract
- Rozšířit existující StepStarted/StepFinished/StepFailed o stage=extraction. Povinné předané run_id a kladný attempt_no, bez page_number. Logický krok scope case/document/run/attempt/stage, stabilní producer-supplied event_id; bez vlastní run/attempt identity nebo odvozování z auditu.
- Allowlist zůstává úzký: skutečně monotónně změřené finite >=0 duration_ms na terminálu; bezpečný technický error_code pouze na StepFailed. Bez nového obecného details/config/result pole, model-call tvrzení nebo počtu vytěžených polí. Nezavádět nové required fields oproti existujícím Step eventům.
- Význam: StepStarted pouze skutečně započatá extrakce nad neprázdným seznamem completed stránek, StepFinished pouze pozorovaný úspěšný návrat, StepFailed pouze skutečně zachycené selhání kroku. Prázdný seznam completed znamená, že se krok neprovedl; nevytvářet skipped/start/success event z absence práce. Platný návrat s prázdnými fields/not_found není automaticky selhání. Lokální extractor není automaticky cloud inference. Tento kontraktový task sám extractor nevolá ani nic neodhaduje z business statusu.
- Ztracený start/AttemptStarted/RunQueued nebrání přijetí doloženého terminálu, ztracený konec unknown. Zachovat conditional event_id idempotenci, document Query a occurred_at jako jediný uložený event timestamp. Všechny změny jsou v interním audit package; business-facing hranice izoluje validaci/serializaci/zápis fail-open.
- Nesmí projít text, fields/hodnoty, quotes/citace, evidence, raw provider responses/errors, celý ExtractionDraft/config/job ani prompt. Chyba jen bezpečný technický kód, bez změny retry rozhodování nebo klasifikace business výsledku.

## Boundaries
Pouze wonderfulkb. Žádný producer hook, změna algoritmu/extractor/worker, model call nebo config, business tabulky/lease/queue/retry/execution změna, outbox, stored projekce/index, deployment/live writes. Checked-in pipeline není doložený nasazený worker; event/store test nedokládá živou extrakci. Doménová jména souborů, ne events.py/state.py/utils.py.

## Verification
Implement the TDD cycle using skill:tdd. Focused fake/Moto: extraction start/finish a start/failure roundtrip, terminal-only fragment, duplicate, dva pokusy/runy oddělené, missing run/invalid attempt/page-scoped extraction/duration/raw business payload odmítnuty bez mutation. Testy významu pracují pouze s explicitně dodanými observations, netvrdí spuštění reálného extractoru; žádné automatické události pro prázdný vstup. NoOp/failing audit boundary nemění caller výsledek. Zachovat source_validation/page/cache kontrakty a všechny registrované gates. Žádná inference, AWS nebo plošná fault matice.
