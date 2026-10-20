---
title: "Attempts GET: souběžné změny vyžadují nové ověření finálního artifactu"
date: 2026-10-20
category: tooling
component: backend
tags: [monitoring, attempts, docker, provenance, deployment]
file_type: rules
---

Při task-dc9a8eab byl nový attempts GET ověřen skutečným RED404 a GREEN31. Po prvním Docker build/smoke přibyl souběžný signature allowlist ve sdíleném facade, step routeru, YAML a smoke. Hashový readback odhalil rozdíl vůči již sestavenému image. Zachovat cizí změny, znovu sestavit final image a spustit instalovaný ASGI smoke jako UID10001 bez sítě; následný plný gate prošel709 testy/1skip. Evidovat zvlášť původní a finální index, runnable manifest, config, wheel a source hash. Fresh AWS worker env se mezitím také změnil: historický chybějící execution/audit env již nebyl aktuální blocker, ale přítomnost env sama není producer-content proof. Pokud existující deployment guard a sdílený request/deploy zůstatek nejsou předané, lokální nuly je neresetují; uchovat aktuální recovery digest/config a vyžádat konkrétní owner převod v témže tasku. Nezaměnit SOURCE/INSTALLED green za DEPLOYED/LIVE-FUNCTION-VERIFIED.