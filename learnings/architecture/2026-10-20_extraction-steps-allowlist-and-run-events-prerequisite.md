---
title: "Extrakce v steps: allowlist a chybějící run-events prerequisite"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, extraction, steps, planning, http]
file_type: rules
---

Při plánování task-12f46945 dne 2026-10-20 existující processing_monitor_step_routes.py již poskytoval jeden bounded evaluated window, run/attempt/type filtr, operation-bound cursor a page delegaci. Extraction zahazoval pouze explicitní OBSERVATION_FIELDS; nový reader nebo handler není potřeba. Sole OpenAPI StepObservation měl samostatné source/page větve, takže obecné Step event stage enumy nestačí pro extraction HTTP kontrakt. Reuse explicitních intake a monitor fixtures umožní genuine RED: authorized HTTP 200 s prázdnými items místo očekávaného terminal-only extraction eventu. Existující step test obsahoval negativní extraction očekávání, které musí být aktualizováno při zachování ostatních stages. V prohlédnutých HTTP modulech a main registraci nebyla run-events route; požadovaná parity je prerequisite blocker, nikoli oprávnění vytvořit zakázaný nový endpoint nebo nahradit event list lifecycle detailem. Historické deployment blockers vyžadují čerstvý preflight; plánovací inspekce neprokazuje současný cloud stav. V tomto běhu vznikl pouze plán, bez testů, implementace či nasazení.