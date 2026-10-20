---
title: "Lifecycle HTTP: fail-closed GREEN není doručená read funkcionalita"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, authorization, tdd, aws, app-runner]
file_type: rules
---

# Lifecycle HTTP: fail-closed GREEN není doručená read funkcionalita

V `be-intake/app/main.py` globální `x-api-key` pouze ověřuje volajícího služby; `require_case` ověřuje existenci case, ale neváže konkrétního volajícího na konkrétní case. Bounded audit reader `audit_queries.read_document` zná pouze case/document a cursor, nikoliv oprávnění. Route může bezpečně vrátit 403 s `Cache-Control: private, no-store`, ale GREEN test takové odpovědi nedokazuje slíbený lifecycle 200, deployment ani obsahový worker→HTTP průchod.

Před povolením lifecycle GET je nutné dohledat skutečný identity→case entitlement a document-in-case lookup u vlastníka HTTP služby; sdílený klíč a existující řádek nestačí. `audit_queries._event_from_item` navíc nezná `ResultPublished`, takže read publication nelze slíbit bez ověřeného producer/decoder kontraktu. Bez přihlašovacích údajů AWS (`NoCredentials`) nelze bezpečně zjistit cílovou App Runner revizi, rollback image ani provést guardovaný deploy. Lokální Docker image/wheel import a RED→GREEN denial testy evidovat odděleně od live akceptace.

Při pytest z `be-intake` použít `PYTHONPATH=../be-document-processing/src ../be-document-processing/.venv/bin/python`; testy z jiných souborů bez importu lokálního `intake` fixture mají setup error a staré monitor 200 sketch testy současně čekají na dosud nedodaný HTTP základ. FastAPI může v `app.routes` vracet `_IncludedRouter` místo přímo adresovatelné `route.path`; registrované path template testovat na příslušném routeru a hlavně ověřit skutečnou HTTP odpověď.
