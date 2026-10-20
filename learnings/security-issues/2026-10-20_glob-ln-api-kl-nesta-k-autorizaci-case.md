---
title: "Globální API klíč nestačí k autorizaci case"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, authorization, fail-closed]
file_type: rules
---

# Globální API klíč nestačí k autorizaci case

Intake API klíč prokazuje přístup k API, ale ne oprávnění volajícího číst auditní data konkrétního case nebo dokumentu. Lifecycle HTTP routes proto lokálně vracely `403` s `Cache-Control: private, no-store`. Před povolením odpovědi `200` je nutné napojit důvěryhodnou vazbu caller→case/document; samotný globální klíč jako autorizační kontrolu nepoužívat.

## Context
Extracted from task: Monitoring lifecycle HTTP: skutečné bounded routes a funkční end-to-end ověření
