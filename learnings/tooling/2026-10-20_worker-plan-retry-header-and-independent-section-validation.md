---
title: "Worker plán retry: canonical hlavička a nezávislá kontrola všech sekcí"
date: 2026-10-20
category: tooling
component: tooling
tags: [compound-plan, monitoring, artifact-validation, retry]
file_type: rules
---

Při retry plánování `task-b0db5177-2f43-4036-b080-af1ca7d143d5` obsahoval původní plán všech sedm povolených sekcí, ale začínal názvem bez `# Plan`; recovery proto skončilo `invalid_header`. Po opětovném spuštění callerem zadaného `plan-path.py --touch` upravit tentýž plán na `# Plan YYYY-MM-DD: title`, nikoli vytvořit další soubor nebo měnit task storage.

Read-only `km_tasks.task.artifacts.inspect_plan_artifact(path, {"projectDir": root})` ověřuje canonical umístění a prefix. Jeho kontrola sekcí používá průnik s rozpoznanými názvy: navíc ověřit každý `##` nadpis proti caller allowlistu a zákaz status markerů. Python skeleton v Markdown lze ověřit přes `ast.parse` bez spuštění testu či vytvoření TDD proof. Projektový `be-document-processing/.venv/bin/python` s `PYTHONDONTWRITEBYTECODE=1` a `PYTHONPATH=/Users/michal/.openclaw/workspace/km-system/lib` zde vrátil `status=valid`.

Výsledek této kontroly je pouze validita plánu. Neprokazuje RED/GREEN, instalaci, deployment ani worker→HTTP funkčnost; ty zůstávají samostatnými implementačními důkazy. Retry plánování také neresetuje již spotřebovaný live budget.
