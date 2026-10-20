---
title: "Monitoring MVP: AttemptStarted v event deníku"
type: implementation
---
# Monitoring MVP: AttemptStarted v event deníku

## Goal
Auditní rozhraní uloží skutečně předané zahájení pokusu, bez vlastního vytváření execution identity.
## Files/functions
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`; nový `be-document-processing/tests/test_monitor_attempt_started.py`. Reference `plans/monitoring/live-trigger-evidence-20261019.md` a `mvp-reference-20261019.md`.
## Change
Přidat AttemptStarted: společná obálka + run_id a povinný skutečný kladný attempt_no. Stabilní event_id předá producer; store zachová existující conditional idempotenci a document Query. Bez inference z ApproximateReceiveCount, počtu audit eventů nebo mutable analysis.updated_at. Událost sémanticky označuje úspěšný owned claim/inkrement; tato změna pouze přijímá doložené hodnoty, claim sama neprovádí. Známý live claim dnes žádný counter neinkrementuje; tento kontrakt netvrdí opak.
## Boundaries
Pouze wonderfulkb. Žádný hook do starého Pipeline.process vydávaný za deployed worker, queue/lease/retry/fencing/business změny, counter allocator ani nový timestamp. Žádné terminal/retry události nebo deployment. Neemitovat ani synteticky nevyrábět producer událost pro živý worker bez doloženého kontraktu.
## Verification
Focused pytest/fake: roundtrip FileReceived+RunQueued+AttemptStarted, duplicate nezvýší počet, missing run/invalid attempt odmítnut bez mutation, druhý run/pokus oddělen. Zachovat registrované gates. Implement the TDD cycle using skill:tdd.
