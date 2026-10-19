---
title: "Case Client: normalizovat filtr názvu právě jednou"
date: 2026-10-19
category: runtime-errors
component: backend
tags: [case-client, normalization, dynamodb, regression]
file_type: rules
---

V Case & Client normalizuje filtr name již společný handler. DynamoDB adaptér jej původně normalizoval znovu, zatímco mock pracoval s jednou normalizací. Normalizace odstraněním právních forem není idempotentní: vstup „Žluťoučká a. a.s. s.“ se nejprve změní na „zlutoucka a. s.“, podruhé na „zlutoucka“. DB pak chybně našla klienta Žluťoučká s.r.o., kterého mock správně nevrátil. Regresní test přes skutečný handler a SDK Stubber nejprve zachytil neočekávanou shodu a po odstranění druhé normalizace prošel. Repository kontrakt přijímá již kanonické filtry; normalizace uloženého názvu při porovnání zůstává sdílená. Při přesunu filtrů přes adaptéry testovat i transformace, které spojí oddělené fragmenty do nového vzoru, nejen běžná velká písmena/diakritiku. Finální lokální sada tohoto tasku měla 47 testů na Pythonu 3.9 i 3.13; cloudové chování z těchto důkazů neplyne.