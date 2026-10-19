---
title: "Case Client: oddělit identitu TDD důkazu, ledgeru a fixtures"
date: 2026-10-19
category: tooling
component: backend
tags: [case-client, planning, tdd, ledger, fixtures]
file_type: rules
---

Při plánování acceptance fixu task-28c88643 byly zjištěny tři odlišné identity: nový follow-up pro proof-capture, helper TASK task-7700299e a sdílený ledger case-global-72fa-20261019-1909 se zachovaným task_id task-72fa674d. Fixture manifest host-case-live-20261019-1820 má navíc vlastní run_id a již vytvořené klienty. Zachovat tyto identity jako provenance; nepřepisovat task_id, nekopírovat staré čítače/deadline/PASS ze fixture manifestu a nezakládat nový cloud budget. Fixture názvy a existující case IDs musejí vstoupit do vyhledávání a per-client očekávání, jinak původní runner hledá pod novým run_id nebo chce znovu seedovat klienty. Nové POST labely musí přežít změnu artefaktu, aby redeploy nepřehrál ne-idempotentní zápisy. Pro chybějící funkce capture skutečný vlastní RED a odpovídající GREEN z explicitního kořene repozitáře; historický identity-only parent proof není jejich důkaz. Zjištěno čtením lokálních souborů při plánování, nikoli live AWS ověřením.