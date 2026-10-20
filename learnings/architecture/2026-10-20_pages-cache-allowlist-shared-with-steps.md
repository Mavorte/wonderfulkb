---
title: "Rozšíření pages allowlistu může nechtěně rozšířit steps API"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, pages, steps, cache-reuse, planning]
file_type: rules
---

Při plánování task-0e56cd5e byl v aktuálním source ověřen import PAGE_TYPES a page_observations z processing_monitor_page_routes do processing_monitor_step_routes (řádky 16 a 61). Přidání PageCacheReused pouze do pages PAGE_TYPES proto současně pustí reuse do steps. Pro read cache increment zachovat explicitně původní steps typy StepStarted/PageCompleted/PageFailed a ověřit skutečným HTTP testem, že reuse-only okno nedává vykonaný krok. Pure audit_page_observations už cache reuse mapuje; nekopírovat mapper ani nepřestavovat bounded reader. Jde o source/planning poznatek, nikoli provedený test, implementaci nebo deployment.