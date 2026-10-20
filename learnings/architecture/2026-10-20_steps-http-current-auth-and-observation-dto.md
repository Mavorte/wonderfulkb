---
title: "Steps HTTP: historický RED a aktuální SERVICE autorizace"
date: 2026-10-20
category: architecture
component: backend
tags: [monitoring, steps, authorization, tdd, openapi, planning]
file_type: rules
---

# Steps HTTP: historický RED potřebuje aktuální autorizační precondition

Při plánování task-252c7fcd dne 20.10.2026 už intake obsahoval `processing_monitor_authorization.authorize_case/authorize_document` a společné `processing_monitor_routes.authorized_document/read_authorized_window`. Middleware pro `/runs/{run_id}/steps` používá SERVICE bearer grant. Historický steps test používající pouze x-api-key proto nyní měří odmítnutou identitu, ne chybějící route.

Pro nový genuine RED reuse explicitní `intake` fixture z `test_monitor_file_received.py` a autorizovaný `monitor` fixture z `test_processing_monitor_routes.py`; teprve authorized nonempty response assertion může prokázat chybějící handler. Historický 404 RED task-72b7dfa9 zůstává platnou historickou evidencí, nepřepisuje se novým auth výsledkem.

Před reuse deklarovaného mapperu ověřit soubory: prohlédnutý audit package obsahoval page mapper a lifecycle reducer, ale žádný pure step mapper. Obecné YAML Step event schemas také nejsou přesný steps observation DTO: sequence je optional, StepFinished vyžaduje duration, zatímco skutečný event ji může nemít. Úzká steps operace potřebuje vlastní observation branches v témže jediném YAML, aby oprava steps kontraktu neměnila ostatní event operace.

Jde o source/planning poznatek; v tomto plánovacím běhu nebyly spuštěny testy ani build/deployment.
