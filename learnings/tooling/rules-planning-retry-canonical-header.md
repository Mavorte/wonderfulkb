---
title: "Plánovací retry: zachovat kanonickou cestu a přesné nadpisy"
date: 2026-10-19
category: tooling
component: tooling
tags: [compound-plan, planning, retry, acceptance]
file_type: rules
---

Při opravě plánovacího tasku Wonderful KB se zachová existující artefakt na cestě vrácené plan-path.py --task-id … --project . --title … --touch; soubor v plans/tasks/ je brief, nikoli výstup plánu. Task task-8e06a0bb-7a44-449d-90f5-b7f22b9fc99a měl předchozí odmítnutí plan_artifact_invalid: status=invalid_header. Při opravě byl úvod sjednocen na # Plan 2026-10-19: … a zkontrolovány přesné sekce Analysis, Approach, Implementation, Testing, TDD, Files, Progress bez status markerů. Callerův užší formát má přednost před obecnou šablonou skillu s Problem, Solutions nebo Files to Modify. Kontrola nadpisů sama nedokazuje úspěch interního recovery validátoru; ten v této session nebyl spuštěn. Obsahový plán, TDD skeleton a host runbook neznamenají provedení implementace, testů či nasazení.