---
title: "Worker HTTP plán: auth fixture musí projít skutečnou validací secret reference"
date: 2026-10-20
category: test-failures
component: backend
tags: [monitoring, planning, tdd, authorization, worker-http]
file_type: rules
---

Při planning retry task-ac9bcb19-d1d0-4bed-a469-f7e503825caf měl TDD skeleton ServiceDocumentAuthorizer s fake Secrets Manager portem, ale secret_arn="local-policy-port". Aktuální AuthorizationSecretSource validuje ARN ještě před voláním portu; taková fixture by skončila autorizační chybou místo zamýšleného behavioral RED na chybějících worker observations. Pro hermetický test použít syntakticky platné lokální ARN a fake secret transport se server-owned SERVICE policy; ponechat skutečný authorizer a membership lookup. To nedokládá live entitlement ani oprávnění měnit host policy. Při revizi skeletonu ověřit validace obalující fake port, nejen jeho návratovou hodnotu. V této session byl opraven pouze plán a canonical plan validator vrátil valid; test ani runtime smoke nebyl spuštěn.