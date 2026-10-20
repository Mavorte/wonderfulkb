---
title: "FileReceived: auditovat jen vlastní potvrzené todo transakce"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, intake, transactions, concurrency, planning]
file_type: rules
---

Při plánování post-commit FileReceived hooku v be-intake/app/main.py rozlišit items (všechny S3 kandidáty) od todo konkrétního úspěšného transact_write_items. Po zrušené transakci může existing obsahovat souběžné vítěze, zatímco items je obsahuje stále. Zachytit přesné todo až po úspěšném návratu transakce a emitovat pouze pro tyto řádky; empty todo, failed commit a concurrent loser neemituje. Listener dostane jen case_id, document_id a received_at potvrzeného řádku; tvorba eventu a fail-open catch zůstávají v interním audit package. Diferenciální test skutečného upload callera má zahrnout smíšený concurrent winner plus vlastní nový řádek a porovnat business writes/pořadí s NoOp i selhávajícím sinkem. Poznatek je ze source inspekce a plánu task-9681bd1b-c317-4f89-ad43-e221f2d05cf6, nikoli z provedených testů či deploymentu.