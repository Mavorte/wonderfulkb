---
title: "Monitoring MVP: události retry a skutečných konců"
type: implementation
---
# Monitoring MVP: události retry a skutečných konců

## Goal
Event/store část `slice-retry-terminal`, proposal `proposal-20261019-150954-c8891f`: RetryEnqueued, AttemptFinished, RunFinished jako explicitní fakta execution runtime, nikoli rozhodování auditu o business retry.

## Files/functions / contract
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`, fail-open boundary; focused `be-document-processing/tests/test_monitor_retry_terminal_events.py`. Předchozí RunQueued/AttemptStarted kontrakty, reference `pipeline.py:45–58,131–146` pouze sémantická, ne deployed worker proof.
- RetryEnqueued: povinný run_id a kladný attempt_no skutečného odcházejícího pokusu; volitelný bezpečný reason_code pouze doložený producentem. Událost vzniká po potvrzeném enqueue, ne queued statusu nebo příslibu retry. Nový pokus netvrdit před claimem.
- AttemptFinished: run_id, skutečný attempt_no; `attempt_status` completed/partial/failed dle skutečně pozorovaného výsledku pokusu. Konec pokusu není konec runu; může po něm následovat retry. Skutečně měřené duration_ms volitelné finite>=0, bezpečný error_code jen doložený.
- RunFinished: run_id a `run_status` completed/partial/failed; attempt_no pouze pokud známý existující pokus. Max-attempt odmítnutí bez nového claimu může doložit konec runu BEZ smyšleného AttemptStarted/nového attempt_no. Chybějící error_code unknown. RunFinished bez attempt scope je legitimní výjimka, ne povolení vynechat attempt u jiných typů.
- Vše má producer-supplied event_id a dokumentovou obálku, bez page scope. Bez generování identit z počtu audit eventů/SQS receive count. Neodvozovat terminal z ticha, Conflict, lease ztráty, S3-only success nebo partial publish. Bez raw business/provider obsahu, exception/config dumpů a kopií jobu.
- Best-effort fail-open i validace/serializace, conditional idempotence event_id, document partition/occurred_at jediné event-time. Přijmout reorder/terminal-only fragment bez úvodních RunQueued/AttemptStarted; neimplementovat execution state machine uvnitř store ani zakazující cross-event existence checks.

## Boundaries
Pouze wonderfulkb. Žádné producer hooky, enqueue/claim/retry/lease/fencing/business/execution změny, outbox/recovery queue/audit replay, cloud/model/deploy, projekce nebo nový index. Jen contract/store, ne runtime lifecycle integrace. Nové moduly doménové, ne events.py/state.py/utils.py.

## Verification
Implement the TDD cycle using skill:tdd. Focused fake/Moto: retry+AttemptFinished+pozdější jiný AttemptStarted, RunFinished různé outcomes, max-attempt run terminal bez nového pokusu, terminal-only/reorder/duplicate/scope izolace, invalid type/status/scope/duration/raw payload odmítnuty. Store nevyrábí enqueue/claim/AttemptStarted ani RunFinished z jiných eventů. NoOp/failing audit boundary nemění caller; předchozí eventy a registrované gates zachovat. Žádný live retry nebo AWS experiment.
