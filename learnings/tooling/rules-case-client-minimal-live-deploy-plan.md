---
title: "Case Client: zjednodušit opakovaný deploy plán podle aktuálních zdrojů"
date: 2026-10-19
category: tooling
component: backend
tags: [case-client, planning, in-place, scope]
file_type: rules
---

Při opravě odmítnutého plánu task-0c4b4cd5-64c3-4bb1-a2dd-a3f712a2fb3f znovu přečti aktuální handler a adaptér: serverové UUIDv4 již byly implementované, zatímco starý plán stále navrhoval jejich zavedení. Pro jednu existující službu stačí lineární účelový deploy skript s explicitním rollbackem a pevný HTTP runner; nepřidávej víceoperační framework, pluginy nebo automatický opravovací engine. Zachovej snapshot, RevisionId, cílové guardy a úplnou live matici jako konkrétní kroky. Review feedback začleň do povolených sekcí plánu; samostatný nadpis Review Feedback porušuje přesný kontrakt hlaviček. Poznatek pochází pouze z plánování a inspekce zdrojů, nikoli z runtime ověření.