---
title: "Audit event dataclass dědičnost a duplicitní definice"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, dataclasses, python, tdd]
---

# Dataclass dědičnost auditních eventů

Při rozšiřování auditních dataclassů nepodtřižuj event s požadovaným `attempt_no` přes rodičovský dataclass, který obsahuje nepovinné pole `run_context`: Python odmítne pořadí nepovinného a povinného pole. Step eventy mají sdílet jednoduchou obálku a validovat run/attempt explicitně.

Zachovej jeden zdroj definic pro každý event. Duplicitní třídy téhož jména mohou způsobit, že `super(ClassName, self)` odkazuje na jinou binding než základní třída instance, případně vyvolá neočekávané `TypeError`. Zachyť tento případ focused pytest RED před opravou a vždy sleduj konkrétní první traceback.
