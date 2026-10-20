---
title: "Monitoring MVP: doložit zdroj triggeru a run/attempt kontrakt"
type: investigation
---
# Monitoring MVP: doložit zdroj triggeru a run/attempt kontrakt

## Goal
Z existujících read-only artefaktů doložit canonical source owner a rozhodnout, zda lze přidat RunQueued/AttemptStarted bez změny business execution modelu.
## Files/functions
Výstup pouze `plans/monitoring/live-trigger-contract.md`. Vstupy `plans/monitoring/live-trigger-evidence-20261019.md`, `mvp-reference-20261019.md`, `docs/architecture/document-processing-aws-contract-differences.md`; existující source/reference v repo jsou read-only.
## Change
Srovnat ověřený live enqueue/claim s checked-in service/bootstrap/pipeline. Dokumentovat source repo/path/revision, skutečnou identitu běhu napříč send→claim, autoritativní attempt_no a success hranice, nebo přesně doložit jejich absenci. Už ověřená fakta: live queue payload nemá run_id/job_id, common claim nemá attempt inkrement; SQS receive count není attempt_no. Nikdy nevymyslet identitu ani prohlásit starý worker za deployed owner. Výstup jedna krátká tabulka known/missing a doporučení nejmenšího navazujícího zásahu; nutnou změnu execution kontraktu předložit jako samostatné rozhodnutí, ne skrytou auditní implementaci.
## Boundaries
Markdown-only investigation existing evidence. Žádné spouštění kódu/testů, AWS/HTTP/provider volání, source import z artefaktů, executable změny, business writes nebo deployment. Chybějící source není povolení založit nový worker. Žádné runtime/task lifecycle instrukce.
## Verification
Každý závěr přesný path/section/hash z existujícího artefaktu, oddělit fakt/inferenci/unknown. Přijatelný výsledek je konkrétní BLOCKED s chybějícím vstupem; není to dodání produceru nebo živého E2E.
