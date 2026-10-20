# Worker instrumentation contract

## Current capability inventory — task-b0db5177, 2026-10-20

The remaining sections are historical pre-execution-owner findings, superseded for current source by this table. None is a claim about a historical deployed image.

| Capability | Actual caller and observed boundary | Current focused evidence / limitation |
|---|---|---|
| RunQueued / AttemptStarted | `common.enqueue_document` after confirmed send / `claim_document` after atomic claim | Real enqueue/claim fixtures, throwing property/listener/sink parity; execution-owner tests cover rejected/ambiguous sends and lost claims |
| Source validation | `run_document`: actual download/size checks and PDF open | Success and safe failure fragments; no source hash/config validation exists, so those checks are not asserted |
| Native pages / extraction | `pdfmod.extract_pages` and completed extraction/render branch | Native PageCompleted, extraction StepStarted/Finished/Failed; no manufactured model calls |
| Transcription | `transcribe_scans`: actual provider port, error, no_vision/budget rejection | PageCompleted/Failed; rejection has no model-call StepStarted; page terminal never creates a second StepFinished |
| Page cache reuse | `transcribe_scans` after UTF-8 decode and consumed transcript/label parsing | PageCacheReused with current run/attempt/page; no model call or PageCompleted; document dedup reuse is not page cache |
| Signature detection | `_signatures` actual `adapters.detect_signatures` and its returned result | StepStarted and Finished/Failed; None/exception fail; disabled/kept-existing emits no detection success |
| Redaction-owned signature detection | `redaction_step.run` | Unsupported audit producer: no detection callback/context interface within this owner; no synthetic replacement detector |
| Publication / run terminal | `run_document` / `_finish_reused` report write + final analysis write after earlier owned writes; `_fail` confirmed failed row/report/readback | ResultPublished/RunFinished only after complete owned writes; failed text/page/report/analysis writes emit no run terminal; `_register_hash` stays fail-open |
| Attempt terminal | `worker_handler.process_document` real pipeline return/exception and downstream case-send failure | AttemptFinished with claim identity and monotonic elapsed duration; original exception and `_remember` behavior preserved |
| RetryEnqueued | SQS-managed redelivery | Unsupported confirmed retry caller; second actual claim proves ordinal 2 independent of receive count, but does not manufacture enqueue observation |
| DLQ/max-attempt run terminal | `dlq_handler.mark_failed` | Unsupported current-generation terminal attestation; no new claim/counter or lifecycle changes |
| Missing dedicated readers | `/runs/{run_id}/events`, `/runs/{run_id}/attempts` | No registered source routes (observed 404); attempts exist inside bounded lifecycle detail, not a fabricated separate endpoint |

Tests: `trigger/tests/test_processing_monitor_worker_http_integration.py` uses real worker/pipeline, central audit/store and existing intake HTTP/auth; only external transports/providers are fake. It covers loss/delay/duplicate/terminal-only transport of producer emissions, not hand-seeded HTTP events. Existing pure observation mappers/read tests remain reused. Build inclusion is proven by `build.sh` staged manifest; final worker-image import is blocked by Docker disk capacity, while final intake wheel/image imports pass. Detailed source/installed/deployed/live status is in `worker-http-deployment-smoke.md`.

## Evidence scope

This is a checked-in source/build contract, not evidence of deployed worker behavior or worker-to-HTTP smoke. The canonical candidate worker is `be-validator-agent/trigger/worker_handler.py` and its pipeline is `be-validator-agent/pipeline/run.py`. The trigger's `build.sh` stages `common.py`, `worker_handler.py`, and pipeline modules; it does not establish provenance for a canonical deployed image/build. Do not infer historical run capabilities from the current environment.

## Supported audit capabilities

**No lifecycle producer boundary is currently supported.** The audit package's events/listener/storage are independent audit capabilities; the actual worker cannot provide the authoritative producer context required to invoke them. No pipeline stage is marked supported merely because a similarly named event or legacy implementation exists.

## Unsupported actual seams

| Actual symbol / caller | Desired event boundary | Required payload | Status and reason | Test / build evidence |
|---|---|---|---|---|
| `trigger.common.Context.send` → `enqueue_document` | `RunQueued` on confirmed enqueue | stable logical run identity and typed confirmed/definite/ambiguous send outcome | Unsupported: send response is discarded; `enqueue_document` exposes no stable run identity and a crash after accepted send is ambiguous. | `plans/monitoring/runtime-producer-context-contract.md`; trigger build stages source but cannot add missing semantics. |
| `trigger.worker_handler.process_document` → `common.claim_document` | `AttemptStarted` on successful claim | immutable `run_id`, atomic `attempt_no` | Unsupported: claim returns status string and updates queued/expired-processing conditionally; no run id, attempt ordinal, or owner token. Failed claims are not starts. | Source inspection; `pipeline/tests/test_pipeline.py` covers pipeline behavior, not claim lifecycle. |
| `process_document` → `_pipeline_run()` → `pipeline.run_document` | terminal attempt/run events | same immutable claim context | Unsupported: call forwards only case/document ids and warm-cached `options()`. Exceptions release the row to queued for retry; returned status is not an authoritative lifecycle identity. | `trigger/worker_handler.py`; trigger source tests are not deployed-worker evidence. |
| `pipeline.run.transcribe_scans` | page/source validation observations | execution context plus page/stage outcome | Unsupported for audit: no context/listener port in `Options` or caller. Existing cache and vision behavior remains business-only; inserting audit without context would invent support. | `pipeline/tests/test_pipeline.py` exercises page behavior, not audit emission. |
| Pipeline extraction, signature, publication | extraction/signature/publish observations | authoritative context and exact confirmed stage outcome | Unsupported: no approved immutable context; pipeline writes text/pages/signatures at separate points, not a single confirmed full-publication boundary. | Source review; no event producer test. |
| `trigger.common.queue_case` / SQS send | `RetryEnqueued` or related enqueue event | confirmed send result and event identity | Unsupported: send response is discarded, no typed confirmed outcome or stable identity. | `runtime-producer-context-contract.md`. |

## Audit package and build inclusion

`be-document-processing/src/document_processing/audit/` contains audit event/listener/storage modules. No canonical worker composition root injects that listener, and the worker artifact does not establish a dependency/build inclusion for the audit package. Adding a no-op adapter, global context, derived identity, receive-count attempt, or new execution mode would not resolve this seam and is intentionally excluded.

The existing pipeline command `python3 -m pytest be-validator-agent/pipeline/tests/test_pipeline.py -q` tests pipeline callers under local fakes. It is not a hermetic worker-artifact build or deployed HTTP smoke. Worker production instrumentation remains blocked until the execution owner supplies canonical build provenance and approves the stable enqueue outcome, atomic claim+attempt identity, and explicit immutable context forwarding described in `runtime-producer-context-contract.md`.
