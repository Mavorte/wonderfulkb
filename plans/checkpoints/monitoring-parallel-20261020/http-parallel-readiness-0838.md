# HTTP parallel-read readiness — 2026-10-20 08:44 Prague

Read-only scheduling evidence review. No task state, source, test, config, deployment, or provider changes. This review adds the requested checkpoint only.

## Verdict: none ready to start before the common HTTP base

**No listed HTTP read task is safe/technically ready to start now.** The existing common base task `plans/tasks/2026-10-20_complete-document-events-http-0818.md` says the actual `be-intake/app/processing_monitor_routes.py` implementation does not exist and identifies the hard blocker: shared `x-api-key` plus case existence is not trusted identity→case authorization. The only current test at `be-intake/tests/test_processing_monitor_routes.py` is a sketch. `be-intake/app/` currently has no `processing_monitor_*` route module; `be-intake/app/main.py` has only the upload API, its shared-key `guard()` and `require_case()` case-existence check. Do not invent auth claims/facade or issue test doubles as trusted authorization. The common base is itself blocked until a real existing authorization seam/owner and authorized synthetic fixture are identified; even after that, its source, focused tests, and gates must be delivered/accepted before dependent HTTP work.

Even a source-disjoint domain module would depend on that absent common auth/document-scope/no-store/error/bounded-reader/router seam. “Can create a separate file” is not actual readiness. The HTTP briefs also each require their own install/deploy/live HTTP acceptance; they cannot be safely combined into parallel mixed revisions on the same App Runner target.

## Candidate scope and dependency groups

### Shared base / first serial group
- **07 run events** — `be-intake/app/processing_monitor_routes.py` facade plus potentially `be-intake/app/processing_monitor_event_routes.py`; reuse `be-document-processing/src/document_processing/audit/audit_queries.py`; update only its own operation in the single OpenAPI YAML; focused HTTP test adjacent to current route tests. Depends on the common base and actual RunQueued/read compatibility (06). Source is explicitly common with 09; these should not race on facade, query, YAML, or the one App Runner target.
- **09 attempts** — same shared facade/event-route module, same `audit_queries.py`, same YAML, attempts-focused HTTP test. Depends on the common run-window/token/auth seam and AttemptStarted compatibility (08), plus 07’s shared route foundation. Not independent of 07 even if a separate endpoint is added.

### Steps branch (one owner in order)
- **11 steps** — owns `be-intake/app/processing_monitor_step_routes.py`, focused tests, and potentially a small facade/main router mount; reuses common auth/reader and `audit_queries.py`; YAML operation. Requires common base plus source-validation event contract (10). It creates the reusable steps adapter/allowlist seam.
- **17 extraction → 19 signatures → 21 publication** — all extend the same steps module/allowlist and corresponding focused test ownership; all touch the single YAML and may touch `audit_queries.py` / shared document/run mapping. Their exact event inputs are 16, 18, and 20 respectively. These are sequential incremental changes, not three parallel HTTP writers. 21 also shares events/steps representation. They cannot start before 11 and their real event contracts are available.

### Pages branch (ordered, with coupling to steps)
- **13 pages** — owns `be-intake/app/processing_monitor_page_routes.py`, page-specific focused tests and small facade/main mount; reuses common auth/reader plus pure `audit_page_observations.py`; may touch shared YAML. Requires base, page-outcome contract (12), and pure page mapper. The pages brief also requires page terminals to be visible in steps, so final integration depends on usable 11 steps seam. It is not ready merely because the pure mapper exists.
- **15 cache-reused** — extends the same page module/allowlist/tests and YAML (no new route); depends on 13 plus cache-reuse event contract (14). Must not race the pages owner.

### Lifecycle branch
- **24 lifecycle** — owns `be-intake/app/processing_monitor_lifecycle_routes.py` and focused tests; small facade/main mount; shares auth/document-scope/no-store/error, bounded reader, `audit_queries.py` and YAML. Depends on base, pure `audit_lifecycle_observations.py` reducer, and actual supported event mappings (06/08/20/22). Domain-file separation reduces direct edits but not the shared router/facade, reader, contract, deployment, or live-proof collisions. It may become a separate source lane only after those concrete inputs and base seam are verified; not now.

## Shared-resource and gate risks

- Intake HTTP facade/router registration (`main.py`/`processing_monitor_routes.py`), `audit_queries.py`, and the sole `be-document-processing/contracts/openapi-processing-monitor.yaml` are shared edit points across several briefs. Exact per-domain modules help source ownership but do not remove the facade registration and compatibility constraints.
- All listed HTTP tasks require own focused FastAPI tests, TDD/review/registered gates, package/build installation, guarded in-place deployment to the same existing App Runner service, and direct feature-specific live HTTP proof. Parallel deploys or mixed-revision smoke on the same target would invalidate provenance and can overwrite each other; deployments/live-proof windows must serialize and preserve recovery/revision guards.
- A stable full/registered test set is a gate, not evidence that arbitrary full tests are safe to run concurrently. Repository currently contains broad uncommitted shared changes; parallel writers/runs risk importing partial code and unstable pytest state. Do not interpret source-file disjointness as isolation of all gates.
- The current base blocker forbids exposing any new endpoint until trusted case authorization is established. Every downstream brief explicitly says to reuse that seam and not fake it.

## Concrete evidence observed

- `plans/tasks/2026-10-20_complete-document-events-http-0818.md`: base route is absent; shared key/case existence fail the stated trust requirement; requires identification of existing authorization interface and safe authorized fixture before implementation/deploy.
- `plans/monitoring/task-9d34c790-5c01-46ba-96d0-bc7f45740763-blocker.md`: prior evidence explicitly records no trusted seam, no route, no install/deploy/synthetic writes, and a non-valid old test run. It is preserved, not relabelled.
- Current `be-intake/app/main.py`: guard checks API key, `require_case()` only confirms case row. No identity-to-case policy/interface found in the relevant source. Current `be-intake/app/` has no `processing_monitor_routes.py` or domain-specific monitor HTTP modules. `be-intake/tests/test_processing_monitor_routes.py` only asserts a mocked endpoint response and cache header; this is not implementation proof.
- Current audit code includes `audit_queries.py`, page/lifecycle pure mapping modules and various event classes, but those pure/event inputs do not supply the absent trusted HTTP base. API route readiness does not follow from their presence.
- Inactive/default-paused batch snapshot `plans/checkpoints/monitoring-parallel-20261020/http-inactive-verified.json` records the HTTP integration continuation inactive; it is historical scheduling evidence, not permission to dispatch.

## Decision and next gate

Keep all listed HTTP candidates held. Do not start any of 07/09/11/13/15/17/19/21/24, and do not dispatch a placeholder/filler implementation. First resolve the existing base task’s concrete authorization/fixture blocker through its owner using real existing platform contracts. Once a safe base implementation is actually present and accepted, re-audit event-source completion, ownership, tests and current App Runner deployment window, then start only the next dependency-ready HTTP candidate(s); serialize shared-source edits and each deployment/live-proof window. No listed endpoint can start before that base.
