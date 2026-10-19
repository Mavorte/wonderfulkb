---
title: "Case Client: úplný fixture inventář před omezenou HTTP sadou"
date: 2026-10-19
category: tooling
component: backend
tags: [case-client, fixtures, http, budgets, acceptance]
file_type: rules
---

Při task-28c88643-682f-4fa4-873f-aeebc8701a1b starý manifest evidoval pouze dva případy prvního syntetického klienta. Druhý znovupoužitý klient již měl tři další případy. Porovnávání jeho HTTP seznamu pouze s novými POST výsledky proto opakovaně čekalo na nemožnou rovnost a spotřebovalo většinu společného limitu200 HTTP.

Před prvními POST načti úplný read-only inventář všech znovupoužitých syntetických client partitions a ověř přítomnost známých ID. Historický manifest není důkaz prázdné partition. Očekávaný seznam je inventář plus nové známé POST výsledky; chybějící známý případ je skutečný BLOCKED. Nevytvářej náhradní klienty.

Po dílčím selhání nikdy neopakuj POST ani neobnovuj budget. Explicitní read-only pokračování smí navázat na konkrétní dokončené výsledky pouze při ověření artifact hash, Lambda revision, Gateway deployment a zaznamenané verze runneru. Uchovej původní failed run i původní runner binding; novým výsledkům přiřaď novou verzi. V tomto běhu tak celkem199 HTTP/9 POST/1deploy prokázalo36 unikátních globálních objektů až do null tokenu a všech11 případů dvou fixture klientů.

Pro šetření requestů zachovej první token během skutečného průchodu v paměti; nečti znovu první stránku pouze kvůli tokenovým negativním testům. Tokeny nikdy neukládej. Evidence: plans/checkpoints/task-28c88643-682f-4fa4-873f-aeebc8701a1b.live-report.md. Výsledek je skutečný deploy a HTTP test, ne pouze source nebo plán.