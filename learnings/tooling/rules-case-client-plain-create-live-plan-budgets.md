---
title: "Case Client: při revizi deploy plánu převést i scénáře a budgety na plain-create"
date: 2026-10-19
category: tooling
component: backend
tags: [case-client, planning, uuid, live-integration]
file_type: rules
---

Při read-only revizi task-0c4b4cd5-64c3-4bb1-a2dd-a3f712a2fb3f mělo OpenAPI verzi 1.4.0, ale aktuální handler stále vyžadoval caller case_id a staré testy očekávaly replay200. Ověřit konkrétní _request/POST flow a testy, nikoli odvozovat připravenost zdrojů z verze OpenAPI. Plán musí podmínit deploy sjednocením se serverovým UUIDv4 a převést celou HTTP matici: repeat201 s jinýmID, same-client souběh201+201 a stejné callerID u různých active klientů také201+201. Sedm základních úspěšných POST spotřebuje sedm case položek; rozpočet12cases/run sdílet napříč deploy iteracemi a rezervovat jej i pro nejisté zápisy. Při timeoutu bez vrácenéhoID nelze GETovat callerID ani slepě opakovat POST; lze pouze bounded query vlastního syntetického klienta/run_id a nevyřešený výsledek je BLOCKED. Při opravě invalid_header zachovat kanonickou cestu a úvod # Plan YYYY-MM-DD: a přesné povolené sekce. Tyto závěry vznikly inspekcí zdrojů a plánu; nejsou důkazem provedených testů nebo deploye.