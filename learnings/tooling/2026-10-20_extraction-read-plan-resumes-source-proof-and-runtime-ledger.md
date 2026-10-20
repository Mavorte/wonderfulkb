---
title: "Extrakční read plán navazuje na současný source a historické důkazy"
date: 2026-10-20
category: tooling
component: backend
tags: [monitoring, extraction, planning, tdd, evidence]
file_type: rules
---

# Extrakční read plán musí navazovat na aktuální source a vlastní historické důkazy

Při opakovaném plánování task-12f46945 dne 2026-10-20 již existovaly extraction větve ve step routeru, focused HTTP testy, skutečná run-events route, kanonický RED/GREEN proof i runtime evidence. Starší plán a learning naopak tvrdily, že extraction allowlist i run-events chybí. Rozhodující je současný kód a datovaná evidence; neplánovat druhý handler ani opakování hotové implementace.

Původní genuine RED zachovat: autorizované HTTP200 vracelo prázdné extraction items. Pokud stejný test nyní projde, jde o characterization GREEN; nový RED vyžadovat jen pro novou prokázanou chybu, nikdy odstraněním hotové funkce. Historický installed image není důkaz nasazení tohoto artifactu. Tasková runtime evidence stále uvádí nepřevzatý deployment guard/shared ledger a chybějící neprázdnou extraction fixture; plán má navázat na původní budget a vyžadovat deployed digest i skutečnou pozitivní HTTP větev.

Před zápisem po plan-path.py --touch přečíst existující kanonický plán: touch neznamená prázdný soubor. Po aktualizaci zkontrolovat celý obsah, právě jeden H1 a jediné aktuální sekce; append nové verze za starou ponechá protichůdné instrukce. V tomto plánovacím běhu byl takový duplicitní obsah odhalen readbackem a nahrazen jediným konzistentním plánem. Zdrojový kód, testy ani runtime se neměnily.
