---
title: "Signature read: veřejný failure kód, image provenance a čerstvé runtime blockers"
date: 2026-10-20
category: tooling
component: backend
tags: [monitoring, signature, tdd, docker, deployment, provenance, budgets]
file_type: rules
---

# Signature read: ověřit celou allowlist → veřejný DTO → image cestu

Při task-095a56a6-1e34-4c79-9649-07a109f27928 reader již dekódoval signature_detection, ale steps observations stage zahazovaly a document/run StepFailed coarsenoval SIGNATURE_DETECTION_FAILED na PROCESSING_FAILED. Úzká oprava potřebovala tři OBSERVATION_FIELDS položky v processing_monitor_step_routes.py, jediný public-code allowlist a tři uzavřené větve v sole OpenAPI YAML. Žádný nový endpoint/reader/producer nebyl potřeba.

Focused HTTP test nad skutečným authorization/membership/AuditStore seamem zachytil genuine RED10 failed/17 passed před produkční editací; stejný argv GREEN27 passed. Parita musí kontrolovat stejné uložené event identity, duration a safe failure kód přes steps/document/run events, terminal-only bez startu a pages exclusion. Obě failure cesty producenta jsou pro read API pouze uložený StepFailed; fake rows nedokládají detector call. Absence/disabled nesmí syntetizovat skipped/success/failure a query musí zůstat jeden evaluated document window s legitimním empty continuation.

## Source a artifact je nutné znovu porovnat po buildu

Souběžný owner změnil sdílený run cursor po prvním úspěšném image smoke. Zachovat jeho source, ponechat původní artifact pod původním tagem a postavit nový final tag; znovu ověřit související HTTP regrese a všechny installed source hashes. V tomto běhu final image obsahoval14 odpovídajících intake/audit modulů. Hash wheelu z package-builder /wheels lze nezávisle porovnat s nainstalovaným importlib.metadata direct_url archive_info SHA256; editable=false a site-packages bez source mount dokazují skutečnou package instalaci, nikoli deployment.

## Čerstvé runtime facts nesmějí zdědit starý blocker ani falešný success

Signed AWS MCP readback nyní prokázal worker EXECUTION_TABLE/AUDIT_TABLE_NAME env, přestože historické handoffy tvrdily jejich absenci. To samo nedokazuje kompatibilní writer/reader chronology nebo signature observation. Přesný granted syntetický document membership read nadále nevrátil Item a canonical JSON-keyed bounded audit Query byl prázdný. Aktivní grant není metadata membership ani kladná live fixture.

Current ingest recovery digest byl stažen a UID10001 import přímo prokázal signature_allowed=false. Kandidát proto nebyl označen deployed jen podle zdravého staršího image. Mrtvý PID v existujícím locku není převod ownershipu nebo sdíleného deploy/HTTP budgetu. Bez těchto vstupů připravit konkrétní final digest/source/config-diff/recovery/native-command handoff v témže zadání a transparentně ponechat DEPLOYED/LIVE-FUNCTION-VERIFIED nesplněné; žádný reset ledgeru, seed/replay nebo vymyšlený run ID.

Tento běh dodal SOURCE a INSTALLED s Python504 passed/backoffice29 passed/build9 funkcí; provedl pouze AWS reads a recovery pull, žádný ECR push/rollout/HTTP/write/inference. Přesná evidence a blokující same-delivery Jackie continuation jsou v plans/monitoring/task-095a56a6-1e34-4c79-9649-07a109f27928-signature-read-evidence.md.
