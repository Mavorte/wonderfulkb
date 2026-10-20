---
title: "Run-events: úspěšný rollout nenahrazuje aktuální syntetickou membership"
date: 2026-10-20
category: runtime-errors
component: backend
tags: [monitoring, apprunner, fixture, authorization, run-events]
---

Při pokračování tasku task-1d77ce99 byl původní App Runner update již SUCCEEDED a service RUNNING na správném ECR digestu. Nebyl potřeba další rollout: ListOperations, DescribeService, ECR digest a installed-image ASGI smoke doložily DEPLOYED.

Historická existence syntetické fixture ale neplatila pro aktuální běh. Token měl stále aktivní hash binding a přesný current document grant, zatímco consistent metadata GetItem vrátil žádný Item. Přímý autentizovaný document-events HTTPS GET pak vrátil404/private,no-store. Nešlo o chybějící přihlášení ani o důkaz pozitivní funkce run-events.

Při resume ověřit nezávisle současnou grant policy, metadata membership, skutečnou event/run observation a image/revision. Grant neprokazuje existenci metadata a úspěšný rollout neprokazuje obsah route. Bez observed run ID nevymýšlet run ani neseedovat audit/replayovat dokument. Udržet stavy SOURCE/INSTALLED/DEPLOYED a LIVE-FUNCTION-VERIFIED oddělené; fixture owner musí dodat podporovanou aktuální cestu v rámci stejné dodávky. Zachovat kumulativní request budget a původní neúspěšné důkazy.