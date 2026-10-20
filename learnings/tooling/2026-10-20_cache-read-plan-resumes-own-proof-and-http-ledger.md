---
title: "Cache read plán navazuje na vlastní TDD a HTTP ledger"
date: 2026-10-20
category: tooling
component: backend
tags: [planning, monitoring, cache, tdd, deployment]
file_type: rules
---

# Při opětovném plánování read slice nejprve načti vlastní evidence

Pro task-0e56cd5e-0911-4acb-bcf6-4df33a97a46c už existují allowlist, mapper, reader registrace, YAML i focused FastAPI test. Vlastní `plans/checkpoints/<task-id>.red-green-proof.md` dokládá skutečný RED (reuse item v pages chyběl) a následný GREEN. Nevyrábět nový RED odstraněním hotové implementace; nové chyby ověřit samostatným skutečným cyklem.

`plans/monitoring/<task-id>-cache-read-evidence.md` obsahuje také recovery provenance a task-wide max. 12 GET. Nová plánovací session tento limit neresetuje; nejprve zkontrolovat novější spotřebu a owner lock. SOURCE/INSTALLED nejsou DEPLOYED ani live důkaz cache-pages DTO.

První bounded audit probes ve staré evidenci použily chybný CASE# klíč. Jejich prázdné výsledky neprokazují absenci observations; použít skutečný `document_key(case_id, document_id)` z readeru, bez Scan nebo fill smyčky. Run/attempt pro HTTP musí vycházet z doložených observations, nikoli z vymyšlených IDs.
