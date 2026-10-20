---
title: "Monitoring MVP: jednoduchý AWS upload → events smoke"
type: implementation
---
# Monitoring MVP: jednoduchý AWS upload → events smoke

## Goal
Malý opakovatelný HTTP smoke skutečné FileReceived cesty: nasazený upload → audit → GET events, bez ručního audit insertu.

## Files/functions
Nový repo-local `be-intake/tests/test_processing_monitor_http_smoke.py`, případně již existující deploy/build entrypoint upravit jen pokud je pro tuto cestu nutný. Vstup: `plans/monitoring/file-received-build-contract.md`, GET `/v1/cases/{case_id}/processing/documents/{document_id}/events`, `plans/monitoring/mvp-reference-20261019.md`.

## Change
HTTP smoke bere adresu/credential a povolený syntetický case serverově z environment, nic nehardcodovat. Jeden malý nový PDF upload, GET events vrátí stejný case/document a FileReceived bez run_id; zopakování stejného uploadu nezdvojí event. Bounded čekání a počet GET. Report jen ID/status a ne-secret artefakt provenance, bez obsahu nebo klíčů. Pokud vstup automaticky spouští nepovolenou placenou inference, explicitně blokovat; nevypínat workera, nevkládat audit přímo.

Existující AWS test cíl eu-central-1; použít skutečný stávající build/deploy postup, bez nového deployment frameworku. Read GET dodávka již zahrnuje skutečné nasazení a HTTP ověření; tento task navíc ověřuje skutečný upload→FileReceived→GET a duplicate chování, není náhradou ani odkladem nasazení GET. Agent provede potřebnou instalaci/in-place test deployment a doladění v rámci tohoto zadání, s recovery artefaktem, zachováním konfigurace a revision/concurrency guards podle AGENTS.md. Jen při skutečném omezení runtime provede Jackie konkrétní operator krok v témže scope, bez source-only uzavření. Bounded syntetické writes jen do určeného case. Výsledek `plans/monitoring/file-received-aws-smoke.md` oddělí lokální test, deployment a skutečný HTTP důkaz. Bez runtime ověření netvrdit nasazený úspěch.

## Boundaries
Jen wonderfulkb. Žádná další funkce API, fault-injection v AWS, full E2E matice, replay skutečných dokumentů, plošná diagnostika nebo business změny. Nespouštět placený provider/replay pro získání smoke důkazu. Auth denial neobcházet.

## Verification
Lokální test smoke harnessu: úspěšná odpověď a bounded chyba, secret není v reportu. Po skutečně ověřeném deploymentu jediný výše popsaný AWS scénář; agent doladí chyby této cesty a doloží skutečné HTTP výsledky, ne pouze harness. Registrované gates zachovat; source/local pass je jiné tvrzení než runtime smoke. Implement the TDD cycle using skill:tdd.

## Společné umístění API
Processing Monitor API je jediný router `be-intake/app/processing_monitor_routes.py` ve stávající službě `wonderfulkb-ingest` (Python/FastAPI, AWS App Runner, eu-central-1), na stejném hostu jako upload. Aktuální test host `https://vt9mavpjky.eu-central-1.awsapprunner.com` je provozní údaj, ne hardcoded default. První operace: `GET /v1/cases/{case_id}/processing/documents/{document_id}/events?limit=50`, pokračování parametrem `next_token`. JSON `items`, `next_token`, `observed_at`. Žádná nová služba, Lambda ani API Gateway; skutečné nasazení a live HTTP ověření jsou součástí read dodávek; tento smoke task se zaměřuje na skutečný post-commit upload→GET průchod.
