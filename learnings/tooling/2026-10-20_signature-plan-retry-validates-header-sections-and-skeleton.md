---
title: "Signature read plán: validovat H1 odděleně od sekcí a skeletonu"
date: 2026-10-20
category: tooling
component: tooling
tags: [compound-plan, signature, artifact-validation, retry]
file_type: rules
---

Při retry task-095a56a6-1e34-4c79-9649-07a109f27928 obsahoval kanonický plán všechny povolené sekce a konkrétní TDD skeleton, ale chybějící prefix # Plan YYYY-MM-DD: vedl k invalid_header. Po opětovném získání stejné cesty přes plan-path.py byl opraven první řádek bez změny task briefu. Read-only km_tasks.task.artifacts.inspect_plan_artifact(path, {"projectDir": project_root}) spuštěný projektovým be-document-processing/.venv/bin/python s PYTHONDONTWRITEBYTECODE=1 a PYTHONPATH=/Users/michal/.openclaw/workspace/km-system/lib vrátil status valid. Nezávislá kontrola potvrdila přesně sedm povolených sekcí, absenci status/WIP markerů a ast.parse Python skeletonu; syntaxe skeletonu není důkaz jeho běhu ani behaviorálního RED. Při aktualizaci plánu znovu ověřit source: aktuální steps allowlist stále neobsahuje signature_detection a events PUBLIC_ERROR_CODES stále nezachovává SIGNATURE_DETECTION_FAILED. Dřívější konflikty či runtime blokery nepřebírat jako aktuálně naměřené; zachovat existující ownership a request/deploy budget. Tento retry provedl pouze plánovací validaci, nikoli pytest, build nebo cloud operace.