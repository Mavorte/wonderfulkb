---
title: "Monitoring pages: autorizovaný RED vyžaduje skutečný caller-to-case seam"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, authorization, tdd, intake]
file_type: rules
---

# Autorizovaný RED pro monitoring GET vyžaduje skutečnou identitu volajícího

V `be-intake/app/main.py` je `guard()` založen na jediném sdíleném `x-api-key`; `require_case()` jen potvrzuje existenci case a platí pouze pro upload. Neexistuje identita volajícího ani jeho entitlement vůči case, document-in-case politika či společná HTTP read route. Mock `cases.get_item` v `test_monitor_file_received.py` proto nikdy sám o sobě nevytvoří autorizovaného synthetic caller. Test očekávající 200 z chybějící pages GET s pouhým tímto klíčem by sice selhal na 404, ale neprokázal správné chování bezpečné route: nelze jej označit za plánem vyžadovaný genuine authorized RED. Helper TDD nespouštět za cenu vymyšlené autorizace.

Praktický postup: nejprve identifikovat vlastníka trusted principal→case rozhodnutí, dokumentové membership politiky a schválené syntetické identity. Teprve s touto fixture zachytit RED přes `skill:tdd`, vystavit endpoint, zachytit GREEN a pak ověřit nasazení. Modulová fixture `intake` není sdílený `conftest`: v pages testu se musí explicitně importovat; `--collect-only` ověří jen fixture setup, nikoliv autorizaci. Lokální venv již obsahoval `multipart` a pytest; AWS CLI v této session vracelo `NoCredentials`, což nezaměňovat s permission denial nebo s deploy úspěchem.
