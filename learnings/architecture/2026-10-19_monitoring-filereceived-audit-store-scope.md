---
title: "Monitoring MVP: udržet FileReceived audit store v úzkém scope"
date: 2026-10-19
category: architecture
component: backend
tags: [audit, dynamodb, monitoring, scope]
file_type: rules
---

# Planování auditu: oddělit kontrakt od implementačního scope

Při plánování prvního FileReceived audit store pomohlo použít `plans/monitoring/mvp-reference-20261019.md` jako rozhodující hranici: interní persistence slice neznamená oprávnění přidat upload producer hook, HTTP endpoint ani deployment. Udržet event envelope přesně omezený na metadata auditu, conditional put pro stabilní event identity a document-scoped Query s bounded pagination; vynechat RunQueued, TTL, fencing, scan a business payload.

Pro testovací plán vycházet z package-level pytest/Moto patternů v `be-document-processing`, ale výslovně rozlišit test lokální mock state od ověření skutečné persistence adapter semantiky. Read exception musí zůstat chyba, nikoli úspěšný prázdný výsledek.
