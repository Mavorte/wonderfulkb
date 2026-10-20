---
title: "GREEN pro bezpečné odmítnutí neprokazuje funkční read route"
date: 2026-10-20
category: test-failures
component: backend
tags: [tdd, monitoring, verification]
file_type: rules
---

# GREEN pro bezpečné odmítnutí neprokazuje funkční read route

RED→GREEN testy prošly pro fail-closed chování a routes byly registrované, ale endpointy stále nevracely požadované bounded observations. Při hodnocení dodávky rozlišovat důkaz bezpečného odmítnutí od důkazu funkčního čtení; ten vyžaduje autorizovanou odpověď, dekódování `ResultPublished` a živé HTTP ověření.

## Context
Extracted from task: Monitoring lifecycle HTTP: skutečné bounded routes a funkční end-to-end ověření
