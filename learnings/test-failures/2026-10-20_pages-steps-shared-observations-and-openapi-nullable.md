---
title: "Pages a steps HTTP musí sdílet observation větve i OpenAPI validátor"
date: 2026-10-20
category: test-failures
component: backend
tags: [monitoring, pages, steps, openapi, tdd, concurrency]
file_type: rules
---

# Pages a steps: ověřovat skutečnou collection proti OpenAPI 3.0

V task-9fcac322-bb59-4168-aa0d-fa45933d3724 prošel nový pages endpoint focused testy, ale souběžná steps změna odstranila jeho dispatch a YAML page branches. Real HTTP parity assertion a následná plná matice chybu zachytily. Při rozšíření steps o PageCompleted/PageFailed musí tentýž pure page mapper zachovat event identity/type právě jednou; přidat stejné pages-specific observation reference do StepObservation, zachovat source_validation assertions a výslovně ověřit nové page observations. Nesyntetizovat StepFinished/StepFailed a nezahazovat terminál bez startu.

Pro celý response envelope používat openapi_schema_validator.OAS30Validator nad jediným YAML. Draft7Validator samotný neumí OpenAPI3.0 nullable a nesprávně odmítne legitimní next_token=null. Neměnit správný response ani druhou specifikaci kvůli tomuto rozdílu validátorů.

Konečná místní evidence: focused32passed, full541passed/1skipped, instalovaný amd64 image ověřen stdin ASGI harness jako UID10001 bez sítě/mountů. To není live delivery: fresh AWS preflight našel pouze pět business tabulek a žádný monitoring secret. Úspěšné STS neprokazuje existenci auditního store/grantu. Ověřit prerequisite a budget před mutation; neoznačit lokální GREEN jako deployed/live success.