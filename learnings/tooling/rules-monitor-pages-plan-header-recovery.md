---
title: "Kanonický monitoring pages plán po invalid_header"
date: 2026-10-20
category: tooling
component: tooling
tags: [compound-plan, invalid_header, recovery, monitoring]
file_type: rules
---

# Kanonický plán po odmítnutí invalid_header

Při opětovném plánování `task-2932fbee-4ac8-47eb-981b-73bbcc17b40f` už existoval obsahově kompletní plán, ale začínal `# Monitoring pages HTTP: …`. Recovery jej odmítlo jako `invalid_header`. Po znovuzískání přesné cesty příkazem `plan-path.py --task-id … --project . --title … --touch` stačilo opravit první řádek stejného souboru na `# Plan 2026-10-20: …`; nepsat nový plán do `plans/tasks/`.

Lokální kontrola `km_tasks.task.artifacts.inspect_plan_artifact(path, {"projectDir": project_root})` v projektovém `be-document-processing/.venv/bin/python` vrátila `status=valid` a sedm sekcí `Analysis, Approach, Files, Implementation, Progress, TDD, Testing`. Kontrola artefaktu neposkytuje důkaz implementace, RED/GREEN ani nasazení. Při recovery zvlášť prověřit přesný seznam všech `##` nadpisů a nepřítomnost status/TODO markerů podle zadání volajícího.
