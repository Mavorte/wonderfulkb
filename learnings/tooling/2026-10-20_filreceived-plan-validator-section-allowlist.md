---
title: "FileReceived plán: oprava invalid_header a kontrola přesného allowlistu"
date: 2026-10-20
category: tooling
component: tooling
tags: [compound-plan, planning, artifact-validation, filereceived]
file_type: rules
---

Při retry task-9681bd1b-c317-4f89-ad43-e221f2d05cf6 znovu vyžádat kanonickou cestu přes plan-path.py a upravit stejný plán. Příčinou invalid_header byl H1 bez prefixu # Plan, přestože všechny sekce již odpovídaly zadání. Oprava na # Plan 2026-10-20: název prošla inspect_plan_artifact s explicitním projectDir přes be-document-processing/.venv/bin/python a PYTHONPATH=/Users/michal/.openclaw/workspace/km-system/lib. Tento validátor kontroluje průnik rozpoznaných sekcí, proto vedle status=valid vždy samostatně zkontrolovat VŠECHNY nadpisy proti uživatelovu přesnému allowlistu; samotný valid neprokazuje absenci dodatečných zakázaných sekcí. Plán obsahoval právě Analysis, Approach, Implementation, Testing, TDD, Files a Progress. Kontrola artefaktu není provedení navržených testů, image buildu ani deploymentu; historické důkazy a task storage zůstávají nedotčené.