---
title: "Signature read vyžaduje steps allowlist i veřejný failure kód"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, signature, steps, planning, http]
file_type: rules
---

Při plánování task-095a56a6-1e34-4c79-9649-07a109f27928 existující audit reader již dekódoval signature_detection Step události, ale processing_monitor_step_routes.OBSERVATION_FIELDS je zahazoval. Rozšíření pouze tohoto allowlistu nestačí pro document/run parity: processing_monitor_routes.PUBLIC_ERROR_CODES pro StepFailed dosud převáděl SIGNATURE_DETECTION_FAILED na PROCESSING_FAILED. Sole YAML měl signature v obecných stage enumech, nikoli ve třech uzavřených StepObservation větvích. Plán proto zahrnuje všechny tři úzké seams a focused FastAPI RED s existujícími explicitními intake/monitor fixtures. Nevytvářet nový endpoint/reader ani producer. Aktuální source obsahuje run-events route navzdory starším learningům o jejím chybění. Historická runtime evidence uvádí ztracenou syntetickou membership, prázdnou audit partition a nepřevzatý guard/ledger; před nasazením vyžaduje nové ověření, nikoli reset budgetu nebo seed. Tento běh vytvořil pouze plán; neprovedl implementaci, testy ani cloud operace.