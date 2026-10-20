---
title: "Run events: reuse document readeru přes scope-bound obal"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, pagination, run-events, planning]
file_type: rules
---

Pro run-events GET v WonderfulKB použij processing_monitor_routes.authorized_document/read_authorized_window/event_dto a stávající AuditStore.read_document. Run-scoped cursor může obalit document-events reader token operací run_events a přesným case/document/run scope; není třeba zavádět druhý reader ani měnit document token format. Filtruj až jediné evaluated okno a zachovej pokračování i při nulovém počtu shod. FileReceived bez run_id do run timeline nepatří. Současná SERVICE politika vrací pro chybějící case grant 403, pro chybějící/cizí dokument 404; neodvozuj status z obecné formulace zadání. Reader EVENT#event_id není globální chronologie a bounded filtering tento kontrakt neřeší. Zjištěno při plánování task-1d77ce99; implementace ani runtime ověření v této plánovací session neproběhly.