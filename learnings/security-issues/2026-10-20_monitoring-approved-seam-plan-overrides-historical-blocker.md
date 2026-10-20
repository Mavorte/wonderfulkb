---
title: "Monitoring: schválený autorizační seam nahrazuje historický blocker"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, authorization, planning, tdd, retained-history]
file_type: rules
---

Při navazování na document-events task použít schválení z 20. 10. 2026 10:01 v autoritativní proposal sekci read-api: konkrétní serverový SERVICE principal a explicitní syntetické case grants se nyní mají dodat. Historický požadavek pouze hledat existující seam už tuto konkrétní implementaci neblokuje; sdílený upload API key ani existence case nadále nejsou entitlement.

Plán musí rozlišovat credential→principal, principal→case a document membership. Pro retained historii samotná absence business řádku nesmí rušit case grant; document scope ale potřebuje přesný důvěryhodný retained záznam s doloženým původem, nikoli pouze vypočtený audit partition key. Ztráta autorizačního zdroje nesmí přejít na staré povolení ani na audit Query.

Při tomto plánování už `main.py:guard` dodával monitoring no-store. Starý skeleton požadující chybějící hlavičku proto nemůže být nový behavior RED. Otestovat skutečně chybějící autorizovaný GET se skutečnou binding logikou a stubem pouze na provider hranici; chybějící fixture není RED. Návrh adaptéru v plánu není důkaz jeho implementace, instalace nebo nasazení.
