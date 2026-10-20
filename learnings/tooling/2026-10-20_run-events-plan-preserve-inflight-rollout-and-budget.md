---
title: "Run-events plán musí navázat na rozběhnutý rollout a zachovat budget"
date: 2026-10-20
category: tooling
component: backend
tags: [monitoring, planning, apprunner, tdd, continuation]
file_type: rules
---

Při plánování task-1d77ce99 už kanonický plán existoval, run_events a focused testy byly ve workspace a task-local proof obsahoval pravý RED404 a GREEN29. Evidence navíc končila přijatým UpdateService bez potvrzení dokončení. Nový plán proto nejprve propojí existující source, proof a artifact s operation ID a při implementačním pokračování vyžádá read-only ověření výsledku operace; nespouští automaticky další rollout ani nemaže route pro nový RED. Pokračuje v již spotřebovaném ledgeru (v poslední evidenci 1/2 rollout a 2/10 fixture reads), nové záznamy započítá před dalším požadavkem. Historický digest a installed smoke nejsou důkazem aktuálně nasazené image ani live obsahové větve. Plánovací session upravuje jen plán a learning, ne cloud stav.