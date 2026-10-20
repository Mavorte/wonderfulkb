---
title: "Sdílený API klíč nestačí pro čtení událostí konkrétního case"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, authorization, case-scope]
file_type: rules
---

# Sdílený API klíč nestačí pro čtení událostí konkrétního case

Intake `guard()` ověřuje jen sdílený `x-api-key` a `require_case()` pouze existenci case při uploadu. Ani úspěšné testy proto nedokazují, že konkrétní volající smí číst document-events daného case. Před zpřístupněním case-scoped GET je nutné důvěryhodné rozhraní pro identitu volajícího a rozhodnutí caller→case, včetně politiky zamítnutí. Do té doby je správné ponechat route uzavřenou odpovědí 403.

## Context
Extracted from task: Monitoring HTTP: dokončit autentizovaný document-events základ a skutečné nasazení
