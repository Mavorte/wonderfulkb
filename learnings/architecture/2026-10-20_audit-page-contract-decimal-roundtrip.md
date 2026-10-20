---
title: "Auditní dataclass roundtrip potřebuje oddělenou obálku a rozsah kroku"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, dynamodb, dataclass, roundtrip]
---

V auditních eventech nesmí StepStarted dědit AttemptStarted jen kvůli run_id a attempt_no: pozdější redefinice AttemptStarted změní identitu třídy a rozbije roundtrip. Sdílej jen FileReceived obálku, celočíselné Decimal hodnoty dekóduj explicitně z itemu včetně attempt_no a page_number, a každý typ dekóduj přes přesný allowlist. Moto Query vrací eventy podle sk=EVENT#event_id, nikoli podle sequence/occurred_at; roundtrip test musí respektovat toto pořadí. PageCompleted/PageFailed jsou samostatné outcome typy, StepStarted pro page_transcription potřebuje kladné page_number; terminal-only fragment musí jít uložit bez předchozího startu.