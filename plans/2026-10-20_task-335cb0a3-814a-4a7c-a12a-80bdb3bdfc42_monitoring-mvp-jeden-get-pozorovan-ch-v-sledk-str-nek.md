# Plan 2026-10-20: Monitoring MVP – pozorované výsledky stránek

Přidat bounded pages observation read do stávajícího Processing Monitor intake API a ověřit skutečnou instalaci, deployment i live chování.

## Analysis

- Vlastnit stránky route/DTO/allowlist v `be-intake/app/processing_monitor_page_routes.py`; zapojit router minimální změnou existující facade.
- Reuse `audit_page_observations.py`, sdílené scope/auth/no-store/error vazby a bounded reader; nevytvářet další store ani Page business objekt.
- Zachovat jediný OpenAPI YAML. Ověřit existující hotové změny a task kontrakty; upravit pouze pages operation/DTO a krokový allowlist.
- Cursor svázat case/document/run/pages/attempt a poslední vyhodnocenou pozicí. Nepoužívat Scan, scan-until-filled ani odvozovat úplnost ze záznamů.

## Approach

1. Prohlédnout relevantní route, reader, observations, OpenAPI a focused tests; reuse hotovou implementaci bez duplikace.
2. Přidat focused testy nejprve a provést TDD pro observations, cursor, scope/error/no-store a krokové terminal mapping.
3. Implementovat jednu GET route s explicitním partial coverage, event observations a bezpečnou paginací; udržet payload bez obsahu dokumentu.
4. Ověřit cílené testy, všechny registrované gates, build/package a instalaci audit package do intake artifactu.
5. Provést guardované in-place nasazení do existujícího `wonderfulkb-ingest` App Runner cíle v eu-central-1: ověřit owner/revision, recovery artifact/config, provenance/digest, concurrency guard a bounded rollout.
6. Ověřit skutečnou route přes bounded autentizované HTTP na oprávněné syntetické fixture; zaznamenat bezpečné status/ID/schema assertions, continuation, no-store a scope/auth negativní případy. Oddělit event producerem doložené live obs. od GET-only ověření; při blokaci uvést konkrétní stav SOURCE/INSTALLED/DEPLOYED/LIVE-FUNCTION-VERIFIED.
7. Zapsat repo-local evidence do `plans/monitoring/`; při chybě opravit v rozsahu, znovu ověřit a guardovaně nasadit, případně rollback ověřeným recovery postupem.

## Implementation

- `GET /v1/cases/{case_id}/processing/documents/{document_id}/runs/{run_id}/pages`: vyžadovat kladný `attempt_no`, limit 1–100, `next_token`; vracet `items`, `next_token`, `observed_at`, `coverage=partial`.
- Mapovat pouze page `StepStarted(page_transcription)`, `PageCompleted`, `PageFailed` s typovanými známými poli. Nezdvojovat terminal page event kroky jako `StepFinished/StepFailed`; zachovat terminal-only/fragment observations.
- Odmítnout malformed/cross-scope cursor; prázdné items s cursor povolit. Read-source failure → 503; authorization/document scope → zavedené 404/403; no-store i chyby.
- Deployment zachová současnou konfiguraci a cizí revizi; žádné produkční/nesouvisející prostředky, broad permissions, ruční audit inserts ani placená inference.

## Testing

- Hermetické focused FastAPI/fake-reader scénáře: dvě stránky, completed/failed, budget-failed unknown method/model, terminal bez startu, dva attempts/runy, malé okno s empty continuation, bounded query count.
- Odmítnutí cross-attempt/operation/run tokenů a malformed attempt; auth/scope/no-store/read 503; ověřit právě jeden page terminal krok.
- Předchozí routes/events i registrovaná gate: `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- Live HTTP ověření přímo nové route/DTO na známé syntetické fixture; bez replayu ne-idempotentních requestů. Read failure testovat hermeticky.

## TDD

Implementační agent použije `skill:tdd`: nejprve doplní focused testy, zachytí RED, implementuje a zachytí GREEN.

**Test file:** `be-intake/tests/test_processing_monitor_page_routes.py` (ověřit existující test layout a navázat na něj; nevytvářet duplicitní suite).
**Framework:** pytest/FastAPI, fake bounded reader.
**Run command:** `pytest be-intake/tests/test_processing_monitor_page_routes.py` (upravit na skutečný repo test runner/layout při inspekci).
**Edit hint:** focused page route tests.

```python
from fastapi.testclient import TestClient

def test_pages_returns_partial_observations_and_continuation(client, page_reader):
    response = client.get("/v1/cases/c1/processing/documents/d1/runs/r1/pages?attempt_no=1&limit=1")
    assert response.status_code == 200
    assert response.json()["coverage"] == "partial"  # RED: route/contract absent
    assert response.json()["items"][0]["event_type"] == "PageCompleted"
    assert response.json()["next_token"]
```

| Test | RED | GREEN |
|---|---|---|
| Partial page observation + continuation | route/contract absent | typed observation and bound cursor returned |
| Cursor/run/attempt isolation + errors | validation/scope behavior absent | invalid tokens rejected; source failures return 503 |
| Terminal page step mapping | duplicate or missing terminal mapping | exactly one observed page terminal event |

## Files

| Path | Change |
|---|---|
| `be-intake/app/processing_monitor_page_routes.py` | Page GET, DTO, allowlist, bounded reader adapter |
| `be-intake/app/processing_monitor_routes.py` / app entrypoint | Minimal router wiring only |
| `be-document-processing/src/document_processing/audit/audit_page_observations.py` | Reuse existing observation mapping; modify only if focused contract requires |
| `be-document-processing/contracts/openapi-processing-monitor.yaml` | Narrow pages operation/DTO and step allowlist updates |
| `be-intake/tests/` focused route tests | TDD coverage for endpoint semantics and safety |
| `plans/monitoring/` | Task-specific deployment and live verification evidence |

## Progress

- [x] Canonical plan path resolved
- [x] Scope and implementation sequence captured
- [ ] Inspect existing code/contracts and reuse completed work
- [ ] Implement via focused TDD and run registered gates
- [ ] Build/install, guard-deploy and verify live HTTP behavior; record evidence/blockers
