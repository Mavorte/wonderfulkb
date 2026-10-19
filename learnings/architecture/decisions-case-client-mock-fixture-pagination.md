---
title: "Case & Client: oddělit mock persistenci od stránkování fixtures"
date: 2026-10-19
category: architecture
component: backend
tags: [case-client, lambda, mock, pagination, planning]
file_type: decisions
---

Při plánování první mock fáze Case & Client je aktuálním rozsahem docs/proposals/proposal-20261019-114433-08800d_case-client-lambda-vyvoj-nezavisly-na-externi-databazi.md (decisions/lambda-mock); plans/case-client-aws.md obsahuje starší DB fázi a není implementačním zadáním. OpenAPI 1.3.0-final zůstává zdrojovým kontraktem. In-memory nově vytvořené cases ani jejich idempotence nejsou sdílené mezi Lambda instancemi; smoke proto čte zabalený fixture case. Náhodný instance-local podpisový klíč kurzorů by navíc zbytečně rozbil i stránkování neměnných fixtures mezi instancemi. Plán proto volí malý verzovaný kurzor se striktní validací schématu, endpointu, klienta, filtrů, limitu a existence pokračovacího ID; kurzor není autentizace ani snapshot. Toto je rozhodnutí z plánování, nikoli runtime ověřené chování. Ověřit jej při implementaci handler/adaptér testem s tokenem nad fixtures přeneseným do nové repository.