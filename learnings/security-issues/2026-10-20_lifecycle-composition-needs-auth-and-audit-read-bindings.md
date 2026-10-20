---
title: "Lifecycle HTTP potřebuje skutečné auth i audit read bindingy"
date: 2026-10-20
category: security-issues
component: backend
tags: [monitoring, lifecycle, authorization, composition, planning]
file_type: rules
---

# Ověřovat oba composition-root bindingy

Při plánování task-ef257fc0-2159-4888-983a-0b30a1dbfe39 obsahovalo intake funkční bounded adaptéry, ale `main.py` neinstaloval ani `lifecycle_authorize_read`, ani `lifecycle_audit_table`. Samotný `audit_listener` je write boundary; jeho existence nezajišťuje funkční čtení. Callback a tabulka instalované testem tuto mezeru zakrývají.

Integrační důkaz musí vytvořit skutečnou aplikaci s konfigurací před importem a nahrazovat pouze klienty Secrets Manager/DynamoDB. Nemá přepisovat authorizer nebo reader. Ověřit credential→SERVICE principal→explicit case grant→document membership→bounded Query a nulový audit read při odmítnutí.

Schválené minimum v monitoring proposal na řádcích 194–196 už dovoluje konkrétní SERVICE adapter a explicitní syntetické granty. Historický checkpoint požadující neurčeného externího providera není důvod znovu plánovat pouze denial. Návrh secret-backed adaptéru v tomto plánovacím běhu není implementace ani živý důkaz.
