---
title: "Retained oprávnění musí zůstat izolovaná při normalizaci SERVICE politiky"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, authorization, service, retained, normalization, tdd]
file_type: rules
---

# Izolace retained oprávnění při normalizaci

Při sdílení autorizace document-events a lifecycle routes se dokumentově omezená SERVICE politika normalizuje na společnou case/principal reprezentaci. Nestačí zachovat pouze allowed_documents: pokud normalizátor sjednotí retained_documents všech credentialů, credential s membership=current získá při chybějícím aktuálním řádku retained oprávnění jiného credentialu pro stejnou dvojici case/document.

Uchovávej retained_by_principal společně s allowed_documents a po autentizaci vyber obě množiny podle přesného credential principalu. Regresní test musí obsahovat dva credentialy ke stejnému dokumentu, current versus retained, chybějící metadata a skutečný HTTP request přes composition root. Current credential musí dostat masked 404 bez audit Query; retained credential může číst jen s vlastním ověřeným provenance záznamem.

V task-ef257fc0-2159-4888-983a-0b30a1dbfe39 tuto chybu odhalil skutečný RED 200 versus 404. Oprava má vlastní archivovaný RED/GREEN cyklus. Při sdílení case helperu navíc zachovej rozdíl mezi invalid identity (403) a maskovaným chybějícím lifecycle grantem (404), aniž změníš jiné route kontrakty.

Zdroj: plans/monitoring/task-ef257fc0-2159-4888-983a-0b30a1dbfe39-lifecycle-http-evidence.md.