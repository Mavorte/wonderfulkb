---
title: "Auditní TDD: fail-open zápis může maskovat chybný roundtrip"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, tdd, roundtrip, fail-open]
file_type: rules
---

Při plánování opravy sdílených auditních eventů ve WonderfulKB začni RED na existujícím sbíratelném Step testu a ověř nejprve `AuditStore.put(event) == "inserted"`, pak konkrétní třídu, rovnost a typ čísel po Moto `read_document`. Store chybu konstrukce/serializace úmyslně převede na `"unavailable"`, takže samotný test equality neukáže místo poruchy. Chybějící PageCompleted import aktuálně způsobuje collection error celé page sady: není vhodným důkazem behaviorálního RED; stránkovou sadu lze opravit až po zachycení skutečné selhávající vlastnosti. Historický host závěr o Decimal decode nepřebírej bez přímého probe: integrální Decimal může být současným dekodérem správně převeden, zatímco duplicitní AttemptStarted a rozdílné dědičné identity zůstávají reálnou vadou.