---
title: "Attempts plán: validovat H1 a všechny sekce nezávisle"
date: 2026-10-20
category: tooling
component: tooling
tags: [compound-plan, attempts, validation, retry]
file_type: rules
---

Při retry task-dc9a8eab-2900-4aca-9a80-4411cebc0472 měl původní plán sedm správných sekcí, ale H1 bez prefixu # Plan vedl k invalid_header. Po opětovném získání kanonické cesty přes plan-path.py byl upraven stejný soubor na # Plan 2026-10-20: název. Validace km_tasks.task.artifacts.inspect_plan_artifact s explicitním projectDir v projektovém Python venv vrátila valid. Tento validátor vyhodnocuje průnik sekcí s allowlistem, nikoli zákaz všech ostatních sekcí: proto navíc ověřit každý nalezený ## nadpis proti sedmi povoleným názvům a zakázané status/TODO/WIP markery samostatně. TDD skeleton lze při plánování syntakticky compile bez spuštění testu. Tyto kontroly nejsou implementační RED/GREEN ani runtime evidence. Zamítnuté čtení compound-plan skriptu nepřekonávat shellovým čtením; spuštění předepsaného helperu a dostupný kanonický validátor postačily.