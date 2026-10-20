---
title: "FileReceived: stabilní identita nezávislá na sequence"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, audit, dynamodb, idempotency]
file_type: rules
---

# Stabilní identita auditního eventu nesmí záviset na sequence

Při plánování FileReceived store porovnat DynamoDB klíč se scénářem opakování stejného event_id se změněnou sequence i occurred_at. Conditional PutItem zabraňuje přepsání pouze stejného pk/sk; pokud sk obsahuje sequence, pozměněné opakování může vytvořit druhý event. Pro tento MVP plán použít document-scoped pk a sk odvozené pouze z event_id, bez dalšího indexu či identity markeru.

Existující test v `be-document-processing/tests/test_monitor_audit_storage.py` ověřuje změnu occurred_at, ale ne změnu sequence. Doplnit cílenou assertion, že i změněná sequence ponechá původní jedinou obálku. Technické pořadí podle event_id nepovažovat za chronologii či kompletní historii.

Zdroj: plán task-4651db4a-86e4-4bd9-ad5d-09532bd16490; jde o návrhové rozhodnutí, nikoli výsledek provedeného storage testu.
