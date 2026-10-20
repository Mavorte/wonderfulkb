---
title: "Monitoring MVP: události jednoho ověření vstupu"
type: implementation
---
# Monitoring MVP: události jednoho ověření vstupu

## Goal
Interní audit přijme a uloží skutečně předané zahájení a výsledek jednoho `source_validation` kroku. Jde o malou event/store část slice 4, ne tvrzení o připojeném živém workeru.

## Files/functions
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`, případně stávající auditní listener pro fail-open předání; nový focused `be-document-processing/tests/test_monitor_source_validation_events.py`. Autorita: proposal `proposal-20261019-150954-c8891f`, sections `data-model`, `instrumentation`, `slice-source-validation`; MVP reference `plans/monitoring/mvp-reference-20261019.md` a source-only poznatky `plans/monitoring/next-slices-source-seams-20261019.md`.

## Change / exact contract
- Přidat pouze `StepStarted`, `StepFinished`, `StepFailed` pro `stage=source_validation`, společnou obálku + povinné předané `run_id`, kladný `attempt_no`. Je to jeden krok config/verze/hash/open, ne událost na každou kontrolu. Identita logického kroku je v tomto slice `(case_id, document_id, run_id, attempt_no, stage)`; eventy mají vlastní stabilní producer-supplied `event_id`. Audit žádnou execution identitu, attempt ani timestamp akce nevytváří.
- Malý typovaný allowlist: `duration_ms` pouze na terminálním eventu a jen je-li skutečně monotónně změřeno (nezáporné finite číslo, jinak neznámé/null); `error_code` jen na StepFailed jako bezpečný technický kód. Referenční kódy checked-in workeru jsou PIPELINE_CONFIG_CHANGED a SOURCE_HASH_MISMATCH; ne raw výjimka/volný popis, S3 cesta, config, hash či obsah. Pro nezmapovanou chybu bezpečný obecný kód, ne serializace výjimky. Žádný `page_number` u tohoto kroku. Nepřidávat obecné details/metadata dump.
- Nevyžadovat přítomnost RunQueued, AttemptStarted ani StepStarted v uložené historii jako podmínku přijetí pozdějšího doloženého výsledku. Ztráta auditu je povolená; terminal-only fragment zůstává čitelný, nevyrábět chybějící event. Persisted idempotence dle event_id, dokumentová partition, occurred_at jako jediný uložený event timestamp a bounded Query zůstávají.
- Chyba validace/tvorby/zápisu při použití auditní business-facing hranice je fail-open; přímý kontraktový validator smí odmítnout malformed event bez mutation. Nespoléhat na catch ve business kódu.

## Boundaries
Pouze wonderfulkb. Žádný producer hook, execution allocator, změna business schématu, lease/retry/queue, runtime, deployment, outbox, backfill ani nový index. Checked-in `be-document-processing/.../pipeline.py:64–73` je sémantická reference, nikoli doložený živý producer; jiný `be-validator-agent/pipeline/run.py` se nesmí potichu zaměnit. Neschválený runtime/outbox návrh v source reportu NENÍ implementační zadání. Jen kontrakt/persistence, ne celý source-validation slice. Nové soubory doménově kvalifikované; žádné events.py/state.py/utils.py.

## Verification
Implement the TDD cycle using skill:tdd. Focused fake/Moto: start→finished a start→failed roundtrip, monotónně předaná duration, duplicate beze změny, terminal-only fragment bez úvodních eventů, missing run/invalid attempt/wrong stage/malformed duration odmítnuty bez zápisu; raw exception/business obsah nesmí projít. NoOp vs failing audit hranice nemění caller výsledek. Zachovat FileReceived/RunQueued/AttemptStarted kompatibilitu a všechny registrované gates. Hermetické testy nejsou live source-validation ani AWS důkaz.
