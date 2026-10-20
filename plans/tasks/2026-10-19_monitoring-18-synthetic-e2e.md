---
title: "Monitoring: prokázat celý syntetický tok a fail-open ekvivalenci"
type: implementation
---

# Monitoring: prokázat celý syntetický tok a fail-open ekvivalenci

## Goal
Dodat hermetický end-to-end důkaz přijetí→queue→attempt→stránky→publish→monitor API/UI a zachování business toku při výpadku auditu.

## Files/functions
Nové `be-document-processing/tests/test_monitor_end_to_end.py`, focused integration fixtures v `be-intake/tests/` a backoffice testech; `plans/monitoring/end-to-end-evidence.md`. Produkční zdroje pouze reference, nezavádět nové funkce ani jiný runner.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Použít malý syntetický PDF a fake OCR/extractor/signature provider, Moto nebo existující lokální adapters, skutečné monitor seams. Happy, partial+retry, cache reuse, chybějící event, pozdní event/refresh, stale owner a smazaný historický artefakt. Ověřit 13 event typů v odpovídajících větvích, bezpečnost case/content a legacy view. Stejný business vstup porovnat se sinkem healthy, NoOp a throwing/timeout: response, business status, publikované hodnoty, retry a lease musí být ekvivalentní mimo původní nondeterministická ID/čas. Evidence uvádí skutečné příkazy/výsledky a source-only limity.

## Boundaries
Žádný live provider/inference, business replay/migrace, test credentials v artefaktech, cloud/deploy operace nebo změny běžných gates. Nezaměnit fake/Moto důkaz za AWS runtime. Neošetřovat nesouvisející chyby oslabením testů.

## Verification
`python -m pytest be-document-processing/tests be-intake/tests -q` v projektovém prostředí dle VALIDATION, `pnpm -C apps/backoffice test`, `pnpm -C apps/backoffice/app test` a `pnpm -C apps/backoffice/app build`; focused end-to-end test samostatně. V reportu matice scénář→API/UI/event/business důkaz a zbývající host live ověření. Při blockeru přesně uvést test a příčinu, nikoli tvrdit úspěch.

Nové Python moduly používat s doménově jednoznačným názvem (audit_/processing_monitor_); žádné nové obecné storage.py, queries.py, utils.py, service.py nebo state.py.
