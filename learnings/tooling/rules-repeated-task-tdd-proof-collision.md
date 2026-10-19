---
title: "Opakovaný TDD cyklus pod stejným task ID koliduje s dokončeným proofem"
date: 2026-10-19
category: tooling
component: backend
tags: [case-client, tdd, evidence, resume]
file_type: rules
---

Při pokračování task-beca6825-147b-43d9-9fb6-694368e70948 existoval kanonický dokončený RED/GREEN proof. Helper proof-capture.py red odmítl nový běh před spuštěním child testů zprávou proof already exists; refusing to replace. Kopie historické evidence na jiné místo sama nepovoluje přepsání původního souboru. Pokud zadání současně vyžaduje nový RED na stejné cestě a zachování původního proofu, je nutné před produkční změnou vyřešit autorizované oddělení cyklu nebo podporu append v helperu. Neoznačovat odmítnuté spuštění za accepted_red a nepoužívat historický GREEN jako důkaz současných změn. V této session nebyl upraven produkční kód ani proveden AWS běh; nové testy zůstaly připravené pro pokračování.