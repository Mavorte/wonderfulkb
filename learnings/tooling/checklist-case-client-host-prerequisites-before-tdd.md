---
title: "Case Client: předpoklady hosta ověřit před TDD a nasazením"
date: 2026-10-19
category: tooling
component: backend
tags: [case-client, preflight, tdd, python, aws-mcp]
file_type: checklist
---

Při implementaci in-place Case Client deploye ověřit před úpravami zdrojů hostem připravenou feature větev: plán současně zakazuje git operace, takže HEAD na main vyžaduje zásah hosta. Dne 2026-10-19 dostupný Python 3.13.7 nestačil k baseline: venv skončil nonzero v ensurepip a základní interpreter postrádal boto3/simplejson. Tyto chyby nejsou platná TDD RED. SAM lint prošel nezávisle; backoffice testy 5/5 prošly, build selhal na chybějícím esbuild. AWS MCP STS potvrdilo účet 609394381050, ale samotné STS neověřuje podporu privátního rollback downloadu ani HTTP transportu. Před obnovením implementace znovu ověřit předpoklady; cloudové mutace a runtime proof nelze odvozovat z lokálních bran. Při blokaci zachovat checkpoint a skutečné výsledky, nevyrábět RED/GREEN artefakt bez provedeného cyklu.