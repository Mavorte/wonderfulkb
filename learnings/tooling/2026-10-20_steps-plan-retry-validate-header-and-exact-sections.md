---
title: "Steps HTTP planning retry: kontrolovat hlavičku i všechny sekce"
date: 2026-10-20
category: tooling
component: tooling
tags: [compound-plan, monitoring, steps, artifact-validation, retry]
file_type: rules
---

Při retry task-252c7fcd-6de4-4406-813b-e7771d61da74 měl existující plán všech sedm povolených sekcí, ale první řádek začínal pouze názvem endpointu. inspect_plan_artifact proto vrátil invalid_header. Po opětovném získání stejné cesty přes plan-path.py stačilo zachovat obsah plánu a změnit první řádek na # Plan 2026-10-20: název. Projektový be-document-processing/.venv/bin/python s PYTHONDONTWRITEBYTECODE=1 a PYTHONPATH=/Users/michal/.openclaw/workspace/km-system/lib následně provedl read-only inspect_plan_artifact(path, {"projectDir": project_root}) se status=valid. Vedle canonical validátoru kontrolovat každý nadpis druhé úrovně proti caller allowlistu: samotný validátor přijímá průnik rozpoznaných sekcí a nemusí odmítnout další nepovolenou sekci. Tyto kontroly ověřují pouze plán, nikoli implementaci, TDD, instalaci nebo AWS nasazení. Při retry zachovat historické proof i spotřebu deployment budgetu; nový plán budget neresetuje.