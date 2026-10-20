---
title: "Intake image: ověřit main import pod skutečným runtime uživatelem"
date: 2026-10-20
category: runtime-errors
component: backend
tags: [docker, intake, packaging, smoke]
file_type: rules
---

Při implementaci FileReceived v task-9681bd1b-c317-4f89-ad43-e221f2d05cf6 image úspěšně sestavil a importoval instalovaný audit package ze site-packages, ale import main selhal PermissionError na /app/main.py: Docker COPY zachoval omezený host source mód, zatímco image běží jako UID 10001. V be-intake/app/Dockerfile použít COPY --chmod=644 pro runtime Python soubory a requirements. Smoke musí ověřit nejen package import, ale také main:app pod výchozím USER, bez source mountu/PYTHONPATH, se sítí vypnutou a AWS_EC2_METADATA_DISABLED=true. Po opravě oba skutečné image importy prošly. Wheel se instaluje non-editable přes pip install --no-deps; audit subset funguje s intake boto3/botocore bez těžkých worker závislostí. Lokální ověření není AWS deployment; přesné příkazy a historie selhání jsou v plans/monitoring/file-received-build-contract.md.