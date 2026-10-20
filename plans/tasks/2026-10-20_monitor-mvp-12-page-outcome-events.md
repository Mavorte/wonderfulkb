---
title: "Monitoring MVP: události nové práce a výsledku stránky"
type: implementation
---
# Monitoring MVP: události nové práce a výsledku stránky

## Goal
Existující audit přijme a uloží pouze skutečně předaný začátek nové práce na stránce a její pozorovaný outcome. Malá event/store část slice 5, bez připojování nedoloženého živého workeru.

## Files/functions
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`, malá stávající auditní hranice podle potřeby; focused `be-document-processing/tests/test_monitor_page_outcome_events.py`. Proposal `proposal-20261019-150954-c8891f` sections `slice-page-outcome`, `signals`, `instrumentation`; source report `plans/monitoring/next-slices-source-seams-20261019.md` pouze fakta, nikoli schválení jeho designových návrhů.

## Change / exact contract
- Rozšířit existující StepStarted o `stage=page_transcription`, povinný kladný page_number. Přidat PageCompleted a PageFailed se stejným stage, run_id, kladným attempt_no a page_number; společná obálka a producer-supplied stabilní event_id. Žádné náhradní run UUID, attempt allocator, inference ze SQS receive count nebo z počtu audit eventů.
- Malý typovaný allowlist: na outcome volitelná skutečně monotónně měřená duration_ms (finite >=0); method pouze native/vision a jen při doložené skutečné cestě, model jen když jej skutečná cesta prokazuje, jinak null/vynechat; bezpečný technický error_code na PageFailed. Model config sám není důkaz volání. Bez free-form provider errors či kopie Page objektu.
- Stránkový StepStarted označuje začátek nové práce, ne cache reuse. PageCompleted/PageFailed je jediný terminální outcome tohoto stránkového kroku; nevytvářet další StepFinished/StepFailed pro stejný konec. Při budget/deadline před voláním není placeholder `Page(method=vision)` důkaz skutečného použití metody/modelu, obojí musí zůstat unknown. Cache-hit není nová inference, PageCacheReused patří zvláštní následující sekci a zde se nepřidává.
- Idempotence podle event identity, oddělení run/attempt/page a occurred_at jako jediný uložený čas. Chybějící start/RunQueued/AttemptStarted nesmí zakázat uložení skutečně doloženého outcome. Ztracený konec zůstává unknown, nezakládat failed podle času ani umělé procento. Neemitovat automaticky žádný nový event z validatoru/store.
- Nepřenášet text/markdown/blocks/tables/visual marks, celé warnings/raw exceptions, rozměry či business výsledek. Žádný artifact resolver/download. Fail-open auditní hranice izoluje i validační/serializační chybu, business tok se nemění.

## Boundaries
Pouze wonderfulkb. Žádný producer hook ani přepis OCR/pipeline/transcribe_scans, žádný cache/queue/retry/lease/execution/business schema change, nové model call, outbox, projekce, deployment či cloud replay. `be-document-processing/.../pipeline.py:89–102` je checked-in sémantická reference odlišná od source `be-validator-agent/pipeline/run.py:125–172,234–248`; nepředstírat shodu se deployed workerem. Nové moduly doménově kvalifikované, bez events.py/state.py/utils.py. Tento kontrakt/store task nedokončuje celý vertikální slice.

## Verification
Implement the TDD cycle using skill:tdd. Focused fake/Moto: native completed, skutečně doložená vision outcome, failed před call s method/model unknown, bezpečný provider error, terminal-only fragment, duplicate, dvě stránky a dva pokusy/runy oddělené; invalid page/attempt/run/duration/business payload bez mutation. Ověřit žádný duplicitní Step terminál a že NoOp/failing audit hranice nemění caller výsledek. Zachovat všechny předchozí eventy a registrované gates. Žádná inference ani AWS, žádná plošná fault matice.
