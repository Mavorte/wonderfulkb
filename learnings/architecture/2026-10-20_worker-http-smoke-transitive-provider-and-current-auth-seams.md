---
title: "Worker HTTP smoke musí zahrnout navazující case krok a ověřit aktuální auth seam"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, worker, http, planning, smoke, authorization]
file_type: checklist
---

Při plánování task-ac9bcb19 dne 2026-10-20 source inspection ukázal, že trigger.worker_handler.process_document po terminálním dokumentu volá case_ready a queue_case. Benignní textové PDF tedy samo neprokazuje nulový rozpočet placených provider volání: před live uploadem ověř i navazující case-step přes existující podporovanou konfiguraci/fixture; nevypínej business krok jen pro smoke. Pokud bezpečný supported vstup chybí, zapiš konkrétní operator blocker. Současně porovnej historická auth blocker hlášení s aktuálním source: intake nyní obsahuje ServiceDocumentAuthorizer s AWSCURRENT SERVICE policy a přesnými document grants, ale existence modulu není důkaz owner schválení, deployed config ani funkčního live HTTP entitlementu. Hermetická policy fixture je pouze fake externí secret port. Plánování zde neprovedlo testy ani AWS operace.