# Independent completion review: shared audit event contracts

**Review time:** 2026-10-20 09:09 CEST (read-only source review; permitted evidence file only)
**Target:** `task-4ad56e72-4cb9-4180-92a0-19e11177c7a8`, whose plan is `plans/tasks/2026-10-20_complete-audit-shared-event-contracts-0818.md`.

## Result: COMPLETE (source-only scope)

Reviewed plan, canonical task checkpoint/proof, current owned audit modules and seven focused tests. Existing task checkpoint claims audit matrix 93, backend 181, backoffice 17/build; independently reran backend and backoffice gates below. The focused tests independently pass, covering the original specified scopes. No source contract gap found in the requested contracts. No deployment/live-runtime obligation applies.

### Current verification
- `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests`: **181 passed**, 5.61s (six dependency deprecation warnings); no collection/environment failure.
- Separate focused files: run_queued **3 passed**; attempt_started **7**; source_validation **8**; page_outcome **14**; extraction **9**; retry_terminal **22**; audit_storage **30**. All pass (same six warnings each).
- `npm --prefix apps/backoffice test`: **17 passed, 0 failed**.
- `npm --prefix apps/backoffice run build`: **bundled 5 function(s)**.
- Canonical proof `plans/checkpoints/task-4ad56e72-4cb9-4180-92a0-19e11177c7a8.red-green-proof.md` documents focused source-validation readback RED (KeyError attempt_no) and matching GREEN command. This is a genuine source regression, not environment failure.

### Scope evidence in current source/tests
- `audit_events.py`: one AttemptStarted definition (lines 193–212); explicit event `to_item` allowlists and `from_item` decoders; event types for source-validation/extraction steps, page outcome, and retry/attempt/run terminal facts. PageCompleted/PageFailed carry page scope, narrow method/model/duration/error allowlists, separate event type, and terminal-only construction. Runtime terminal status/attempt validation is explicit and does not infer state. Decimal integer decoding normalizes integral values through `_integer` / `_attempt_values`.
- `audit_storage.py`: accepts all event types, preserves conditional event-id idempotency and fail-open writes; `audit_queries.py:80–97` dispatches all persisted event types, including PageCompleted/PageFailed and runtime events. Bounded document Query remains intact.
- Focused test evidence: `test_monitor_attempt_started.py` roundtrip/dedup and distinct attempts; source-validation tests include terminal-only, roundtrip, malformed input; page-outcome tests include roundtrip/terminal-only/dedup/scope separation and invalid payload; extraction tests include finish/failure, terminal-only, dedup and invalid payload; retry-terminal tests include order/terminal-only/all statuses and malformed facts. `test_monitor_audit_storage.py` retains bounded query, document scope, duplicate behavior, validation and outage behavior. RunQueued/FileReceived compatibility tests remain included.

### Caveat / not a scope failure
The run-queued, attempt, step, page, and runtime classes do not use a single literal serializer/decoder implementation; they each implement explicit allowlists and share small normalization helpers where appropriate. The plan's operative requirement is one definition per event type and explicit allowlisted serialization/deserialization, which current source satisfies. No redesign required. There is no fresh independent rerun of the combined 93-test audit matrix captured in this review; checkpoint records it, while the full backend (181) and each focused file passed now.

No implementation changes made. No deploy or live writes performed.