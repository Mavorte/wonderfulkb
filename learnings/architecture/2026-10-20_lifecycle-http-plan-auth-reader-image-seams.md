---
title: "Lifecycle HTTP: plán odděluje specifikaci od bezpečně nasazené route"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, fastapi, audit, authorization, planning]
file_type: rules
---

# Lifecycle HTTP: plán musí rozlišit specifikaci, reducer a skutečně provozovanou route

Při plánování `task-a67c7b62-949e-4720-b1a2-51fcc3502cec` už OpenAPI specifikovala runs/detail/audit, čistý reducer existoval a focused pytest soubor obsahoval očekávání 200. V `be-intake/app/main.py` však žádná monitorovací route nebyla; globální `x-api-key` a existence case nedokazují oprávnění konkrétního volajícího ke case. Test s 200 a klíčem proto nelze povýšit na zelenou implementaci, dokud se nepotvrdí skutečný trusted caller→case/document seam.

Pozor na odlišné kontrakty v jednotlivých vrstvách: `audit_queries.read_document()` zná jen dokumentově vázaný cursor a jeho event dispatch v daném checkoutu neregistruje `ResultPublished`; reducer vrací `RunObservation.state` a `PublishedResultObservation.evidence`, nikoli hypotetické `status` a `outcome` ze sketch testu. Operation-bound cursor patří úzkému HTTP adaptéru; tvrzení o publikaci musí odpovídat skutečně dekódovanému eventu. `be-intake/app/Dockerfile` instaluje audit wheel, ale nově přidaný route modul se do image nedostane bez explicitního `COPY`.

Při další implementaci nejprve doložit auth/read/producer interface, potom získat skutečné RED pomocí importovaného `intake` fixture a dostupného processing venv; pouze skutečně guarded, nainstalovaný a přímo přes HTTP ověřený image může být označen jako doručený.
