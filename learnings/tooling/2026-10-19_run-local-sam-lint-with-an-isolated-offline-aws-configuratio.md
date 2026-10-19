---
title: "Run local SAM lint with an isolated offline AWS configuration"
date: 2026-10-19
category: tooling
component: backend
tags: [sam, lint, aws, offline]
file_type: rules
---

# Run local SAM lint with an isolated offline AWS configuration

SAM template lint passed using an explicit region, disabled EC2 metadata lookup, empty AWS configuration paths, placeholder credentials, and disabled telemetry:

```sh
AWS_REGION=eu-central-1 \
AWS_DEFAULT_REGION=eu-central-1 \
AWS_EC2_METADATA_DISABLED=true \
AWS_CONFIG_FILE=/dev/null \
AWS_SHARED_CREDENTIALS_FILE=/dev/null \
AWS_ACCESS_KEY_ID=offline \
AWS_SECRET_ACCESS_KEY=offline \
SAM_CLI_TELEMETRY=0 \
sam validate --lint --template-file be-case-client/template.yaml
```

Reuse this configuration for local template lint when validation should be independent of the developer's AWS credential chain. A successful lint result establishes template validity, not deployment authorization or runtime readiness.

## Context
Extracted from task: Case & Client: nasadit náš Python na existující testovací API a odladit živou DB integraci
