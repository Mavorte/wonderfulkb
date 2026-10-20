---
title: "Lifecycle HTTP: provider-gated lokální GREEN není live oprávnění"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, authorization, cursor, tdd, aws]
file_type: rules
---

# Provider-gated lifecycle route není doložené oprávněné nasazení

V intake `main.py` ověřuje sdílený `x-api-key` pouze identitu služby; `require_case` ověřuje existenci, ne právo číst case. Lokální TDD může vložit `app.state.lifecycle_authorize_read` a `lifecycle_audit_table`, a tak prokázat mapper, jeden bounded read, scoping cursoru a 503 při výpadku. Tato injekce ale není produkční autorizace ani end-to-end důkaz. Bez skutečného poskytovatele musí výchozí cesta zůstat 403 bez čtení auditu. Provider má vydat přesný `AuthorizedDocumentScope` až po ověření caller→case entitlement a příslušnosti dokumentu; pouhý tuple či podvržené ID odmítnout.

Opaque HTTP continuation balí reader cursor společně s operací/case/document/run. Před voláním čtečky validovat také vnitřní reader token proti dokumentovému klíči; jinak chybně zakódovaný token spadne do obecné větve 503 místo požadovaného 400. Zachovat původní `LastEvaluatedKey` i pro prázdné vyfiltrované okno.

Při nepřítomnosti AWS credentials (`NoCredentials`) nelze znát aktuální App Runner revision/recovery, proto lokální image digest není deployed digest. V tomto případě vést SOURCE, INSTALLED, DEPLOYED a LIVE-FUNCTION-VERIFIED odděleně, bez dodatečného tvrzení o publikaci, dokud není producer/reader kontrakt `ResultPublished` doložený.
