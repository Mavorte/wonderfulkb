---
title: "Worker HTTP: aktuální auth fixture a execution prerequisite ověřovat odděleně"
date: 2026-10-20
category: test-failures
component: backend
tags: [monitoring, worker, http, authorization, tdd]
file_type: rules
---

Při ověření task-ac9bcb19 dne 2026-10-20 prošlo 385 testů pipeline/intake/audit, ale dvě existující page/steps fixtures očekávaly HTTP200 pouze s x-api-key a dostaly HTTP403. Source ServiceDocumentAuthorizer přitom existoval; nelze opakovat historické tvrzení, že trusted source seam chybí, ani oslabit autorizaci kvůli staré fixture. Live entitlement tím nebyl prokázán.

Trigger suite spuštěná z be-validator-agent/trigger příkazem env PYTHONPATH=..:../../be-document-processing/src ../../be-document-processing/.venv/bin/python -m pytest -q tests již neměla historickou backfill collection chybu. Selhal však pre-existing test execution_context parametru: skutečný process_document měl pouze ctx/message. Context.send nadále zahazoval SQS odpověď a claim vracel string bez run/attempt identity. Před full-path behavioral RED je tedy potřeba owner interface uvedený v autoritativním plánu; starý signature test ani neautorizovaná HTTP fixture nejsou náhradou task-scoped RED/GREEN. Zapsat konkrétní blocked stav, ne vyrábět proof či fake runtime identity. Nebyl proveden deploy ani live HTTP.