---
title: "Steps cursor: skutečný RED musí odmítat duplicitní scope, ne chybnou error envelope"
date: 2026-10-20
category: test-failures
component: backend
tags: [tdd, fastapi, cursors, proof, monitoring]
file_type: rules
---

Ve WonderfulKB intake HTTPException handler vrací error, nikoli výchozí FastAPI detail. Test nesmí použít špatnou envelope jako implementační RED. V tomto pokračování helper takový fail mechanicky zachytil; byl explicitně označen jako test-only, opraven bez produkční změny a zachován v historii. Ani hluboký token v dovolené velikosti nepřinesl behaviorální fail, proto passing RED helper správně odmítl. Skutečnou mezerou byl platný emitted steps cursor doplněný o dvě konfliktní attempt_no hodnoty: json.loads použil poslední a HTTP vrátil200 s další Query. Test-first očekávání400/private,no-store/no-second-Query vytvořilo genuine RED; úzký object_pairs_hook odmítající duplicitní keys zajistil GREEN17. Použít helper --start-new-cycle, zachovat původní extraction proof v archivech, přečíst RED před production edit a current proof po širších gates. Helper exit0 s accepted_red sám nezaručuje správné očekávání testu; assertion musí odpovídat skutečnému kontraktu.