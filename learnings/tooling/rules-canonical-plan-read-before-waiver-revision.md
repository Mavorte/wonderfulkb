---
title: "Kanonický plán po TDD waiveru revidovat místo připojení druhého plánu"
date: 2026-10-19
category: tooling
component: tooling
tags: [compound-plan, waiver, tdd, canonical-path]
file_type: rules
---

Při plánování task-ba84dff1-cb7e-41c4-b12c-01aefd9591db vrátil plan-path.py --touch již existující plán s historickou povinností dohledat stub RED. --touch nezaručuje prázdný soubor: před zápisem vždy přečíst vrácenou cestu a revidovat její obsah, nepřipojovat druhý plán. Po výslovném waiveru Michala z 2026-10-19 nahradit zrušené instrukce v aktivním kanonickém plánu přesným tdd: skip a požadovanou sekcí TDD; nezměnit původní rodičovský plán ani proof/checkpoint/evidence artefakty. Zachovat běžné funkční testy a nezávislou acceptance. Waiver není potvrzením historického proofu. Závěrečný readback musí ověřit jedinou hlavičku plánu a absenci starých aktivních požadavků na RED.