---
title: "Plánovací retry: ověřit také úvodní H1, nejen povolené sekce"
date: 2026-10-19
category: tooling
component: tooling
tags: [compound-plan, invalid_header, planning, recovery]
file_type: rules
---

Při recovery task-beca6825-147b-43d9-9fb6-694368e70948 měl existující kanonický plán všechny povolené sekce Analysis, Approach, Implementation, TDD, Testing, Files a Progress, ale začínal nadpisem # Case Client: místo šablonového # Plan 2026-10-19:. To odpovídalo hlášenému invalid_header. Po získání cesty přes povinný plan-path.py nejprve přečíst existující soubor a opravit H1 na # Plan YYYY-MM-DD: název; nezakládat další plán a nezasahovat do plans/tasks ani lifecycle stavu. Samostatně zkontrolovat přesné H2 a nepřítomnost Status/TODO/WIP markerů. V této session byla struktura zkontrolována lokálně, nikoli externím acceptance validátorem; implementace ani AWS operace neproběhly.