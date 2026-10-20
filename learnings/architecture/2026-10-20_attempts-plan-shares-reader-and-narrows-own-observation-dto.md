---
title: "Attempts GET plán: samostatné observation DTO nad sdíleným run cursor codec"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, attempts, pagination, planning]
file_type: rules
---

Při plánování task-dc9a8eab-2900-4aca-9a80-4411cebc0472 existoval AttemptStarted decoder, AuditStore.read_document a run-events handler, ale attempts route chyběla. Reuse authorized_document/read_authorized_window a jediný evaluated Query; striktní run cursor codec lze parametrizovat operací s kompatibilním defaultem run_events a novou hodnotou attempts. AttemptObservation v jediném OpenAPI YAML původně odkazuje na plný AttemptStarted: pro požadované tři položky event_id/attempt_no/occurred_at změnit pouze vlastní DTO, nikoli obecný event kontrakt. Distinct event IDs se stejným attempt_no zůstávají oddělenými observations, ne business stavem. Pro budoucí live ověření načíst poslední run-events evidence: historická syntetická fixture již při skutečném GET vracela404 kvůli chybějící membership; existence grant policy není důkaz existence dokumentu nebo runu. Tato session vytvořila pouze plán, ne implementaci ani runtime důkaz.