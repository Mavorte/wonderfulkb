---
title: "Planning retry: validovat první řádek i kanonické umístění"
date: 2026-10-20
category: tooling
component: tooling
tags: [compound-plan, artifact-validation, planning, retry]
file_type: rules
---

Při retry task-4651db4a-86e4-4bd9-ad5d-09532bd16490 měl plán správné sekce, ale první řádek bez prefixu # Plan způsobil invalid_header. Znovu získat cestu přes plan-path.py, přečíst existující plán a opravit hlavičku na # Plan YYYY-MM-DD: název; zachovat stejný soubor. Před předáním použít km_tasks.task.artifacts.inspect_plan_artifact s projectDir a navíc ověřit všechny nadpisy proti přesnému seznamu povolených sekcí. Zde výsledek valid potvrdil hlavičku, sekce i umístění pod plans/. Systémový python3 import validátoru odmítl kvůli verzi pod 3.10; projektové be-document-processing/.venv/bin/python validaci provedlo úspěšně. Jde o kontrolu plánovacího artefaktu, nikoli spuštění pytest či důkaz implementace; task state ani historické TDD proofs se ručně nemění.