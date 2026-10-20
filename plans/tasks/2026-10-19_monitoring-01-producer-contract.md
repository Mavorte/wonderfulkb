---
title: "Monitoring: doložit producenty, ingest routing a autorizační hranici"
type: investigation
---

# Monitoring: doložit producenty, ingest routing a autorizační hranici

## Goal
Z existujících zdrojových artefaktů dodat rozhodnutelnou mapu producentů a integrace do `plans/monitoring/producer-contract.md`; oddělit prokázanou zdrojovou vazbu, doložený runtime a skutečně neznámé údaje.

## Files/functions
Číst `docs/architecture/document-processing-aws-contract-differences.md`, `be-intake/app/main.py`, `be-intake/template.yaml`, `be-document-processing/src/document_processing/{bootstrap,service,pipeline,api,aws_handlers}.py`, `be-document-processing/template.yaml` a `apps/backoffice/functions/lib/awsApi.ts`. Zápis pouze uvedený markdown v `plans/monitoring/`.
Kontrakt (read-only kromě výslovně uvedených upřesnění): `docs/proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md` a `be-document-processing/PROCESSING-MONITOR-API.md`, `be-document-processing/contracts/openapi-processing-monitor.yaml` revize 0.3.2.

## Change
Popsat konkrétní ingest commit bod, vlastníka analysis, vstup workeru, identity case/document/run, předání FileReceived do interního audit listeneru, a serverovou case/content autorizaci včetně zdroje důvěry. AWS dvojice `(case_id, document_id)` má přednost před starým adaptérem. Pro každou vazbu citovat cestu/funkci a určit nejmenší integrační seam a přesný potřebný host důkaz, pokud není v artefaktech. Zdroj DocumentService není důkaz propojení s intake. Nenavrhovat novou službu nebo domýšlené user claims.

## Boundaries
Pouze zdrojová analýza, žádné testovací/runtime příkazy, cloud, credential čtení nebo změny mimo plans. Žádné předstírání živého ověření.

## Verification
Zkontrolovat v reportu úplnost matice producer→ID→commit→audit seam→oprávnění→reference. Každé nedoložené nasazení/auth propojení má explicitní unknown a konkrétní požadovaný důkaz. FileReceived nelze zaměnit za complete_upload jiného flow. Výstup musí jmenovat použitelný adaptér, nebo přesně chybějící technický vstup; ne obecné doporučení.
