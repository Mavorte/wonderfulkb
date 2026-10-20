---
title: "Pages HTTP adapter musí před mapperem odfiltrovat unscoped a cache události"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, pages, mapper, planning]
file_type: rules
---

Při plánování pages HTTP task-9fcac322 byl ověřen audit_page_observations.to_page_observations: validuje run_id a attempt_no každého vstupu ještě před event-type filtrem a už zahrnuje PageCacheReused. Celé bounded dokumentové okno proto nelze předat přímo: FileReceived bez runu vyvolá chybu, cache observation by rozšířila scope řezu. HTTP adapter nejprve vybere přesný run/attempt a typy StepStarted(stage=page_transcription), PageCompleted, PageFailed a teprve tento konečný seznam předá stejnému pure mapperu. LastEvaluatedKey continuation se přitom musí zachovat z původního vyhodnoceného okna i při prázdném seznamu. Nevyrábět druhý Query ani neodstraňovat existující cache podporu z package. Jde o ověřený source/planning poznatek; v tomto běhu nebyla provedena implementace, test execution ani AWS deployment.