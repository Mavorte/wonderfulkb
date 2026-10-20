---
title: "Chybějící fixture není behaviorální TDD RED"
date: 2026-10-20
category: test-failures
component: backend
tags: [tdd, fixtures, authorization]
file_type: rules
---

# Chybějící fixture není behaviorální TDD RED

Původní intake sketch selhal na chybějící pytest fixture ještě před spuštěním ověřovaného chování. Takové selhání nelze použít jako důkaz TDD RED. Pro autorizační scénář je navíc potřeba autentizovaná syntetická fixture s oprávněným volajícím a case/document; pouhé mockování existujícího case oprávnění neprokazuje.

## Context
Extracted from task: Monitoring HTTP: dokončit autentizovaný document-events základ a skutečné nasazení
