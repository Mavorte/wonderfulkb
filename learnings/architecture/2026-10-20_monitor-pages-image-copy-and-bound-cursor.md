---
title: "Monitorovací pages route vyžaduje image copy a scope-bound cursor"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, intake, docker, cursor, authorization]
file_type: rules
---

# Monitorovací route potřebuje dva nezávislé integrační kroky

Při plánování pages GET v tomto checkoutu nestačí přidat router do `be-intake/app/main.py`: `be-intake/app/Dockerfile` kopíruje do runtime image jen `main.py` a `content_hashes.py`. Nový doménový `processing_monitor_page_routes.py` se musí dostat do image a jeho import se musí ověřit z hotového image bez bind mountu; lokální TestClient to neprokazuje.

`audit_queries.read_document()` už nabízí jediné bounded Query a last-evaluated continuation, ale jeho token nese `operation=document_events` a case/document, nikoli run/attempt/pages. Pages adapter proto musí navázat vlastní cursor na case/document/run/attempt/operation a zabalit skutečnou poslední vyhodnocenou pozici, i když filtrované okno vrátí prázdné items. Nezavádět druhé Query pro doplnění stránky.

Než se route vystaví, ověřit skutečný caller→case authorization seam: sdílený x-api-key a existence case v aktuálním `main.py` tuto vlastnost nedokládají. Chybějící seam je konkrétní blocker, nikoli důvod pro fallback auth nebo green tvrzení.
