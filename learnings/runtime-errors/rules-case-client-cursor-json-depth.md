---
title: "Case & Client: délkový limit kurzoru neomezuje hloubku JSON"
date: 2026-10-19
category: runtime-errors
component: backend
tags: [case-client, pagination, json, offline-tests]
file_type: rules
---

V be-case-client/src/case_client_mock_repository.py má next_token limit 4096 znaků, striktní base64url a přesné verzované schema. Přesto se do limitu vejde JSON s 1100 vnořenými poli, který json.loads odmítne přes RecursionError. Původní mapování zachytávalo ValueError/TypeError, takže handler vracel sanitizovanou 500 místo požadované 400. Oprava zachytává také RecursionError uvnitř dekódování kurzoru a převádí ji na InvalidRequest; provozní chyby repository se nadále mapují na 500. Integrační test test_pagination_query_binding_and_cross_repository přes skutečný handler a adaptér nejprve prokázal 500 != 400 a po opravě prošel. Finální offline sada měla 18 úspěšných testů. Při dalších změnách tokenů testovat i malý, ale hluboce zanořený payload, nejen překročení délky nebo neplatnou base64. SAM/gateway cloudové chování tímto testem ověřeno není.