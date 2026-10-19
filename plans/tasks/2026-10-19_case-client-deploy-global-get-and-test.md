---
title: "Case Client: nasadit GET /cases a prokázat funkčnost přes HTTP"
type: implementation
---
# Case Client: nasadit GET /cases a prokázat funkčnost přes HTTP

## Cíl
Ty sám dokonči a nasaď globální GET /cases do existujícího AWS testu a otestuj ho přes HTTP. Samotné lokální testy ani připravený guard nejsou výsledek. Uživatel19:34 výslovně požaduje nový samostatný implementační pokus včetně deploye agentem.

## Soubory
Měň existující `be-case-client/tools/case_client_test_deploy.py`, `be-case-client/tests/integration/case_client_api_integration.py` a jejich testy. Handler/repository už GET /cases implementují. Ověřený Python: `/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python`; boto3/simplejson i AWS preflight fungují. SAM: `/Users/michal/.local/bin/sam`.

## Změna
Dokonči chybějící additive Gateway GET/AWS_PROXY a globální scénáře runneru; sestav Linux cp313/x86_64 balíček, nasaď a proveď HTTP testy. Technické podklady jsou v `plans/2026-10-19-2_plan-2026-10-19-case-client-global-get-acceptance.md`; nový aktuální plán musí zahrnout celý postup níže, nikoli pouze guard. Nezastavuj po dílčí úpravě budget guardu.

## Konkrétní nástroje a postup (upřesnění uživatele19:36)
Použij existující OpenCode Read/Grep pro orientaci, Edit/apply_patch pro změny a Bash pro příkazy. Nevytvářej druhý deploy framework. Z kořene repozitáře:
```sh
PY=/Users/michal/.openclaw/tmp/opencode/case-client-venv/bin/python
# Po doplnění testů/implementace:
"$PY" -m unittest discover -s be-case-client/tests -p 'test_*.py'
"$PY" -m compileall -q be-case-client/src be-case-client/tools be-case-client/tests
/Users/michal/.local/bin/sam validate --lint --template-file be-case-client/template.yaml
# Až opravené nástroje bezpečně podporují pátou metodu a ledger:
"$PY" be-case-client/tools/case_client_test_deploy.py preflight
"$PY" be-case-client/tests/integration/case_client_api_integration.py --baseline
"$PY" be-case-client/tools/case_client_test_deploy.py deploy --allow-writes --run-id case-global-72fa-20261019-1909
"$PY" be-case-client/tests/integration/case_client_api_integration.py --allow-writes --run-id case-global-72fa-20261019-1909
"$PY" be-case-client/tools/case_client_test_deploy.py verify
```
- Helper `build()` už zajišťuje Linux cp313/x86_64 závislosti, ZIP/hash; `snapshot()`, `apply_update()`, `require_revision()`, `reserve()` a `private_write()` poskytují snapshot, Lambda update a guardy. Reuse je, zkontroluj vhodnost, nedělej slepý `sam deploy`.
- Chybějící Gateway krok IMPLEMENTUJ v témže helperu přes `session().client('apigateway', config=CONFIG)`: `get_resources` najde existující `/cases`; `get_method`/`get_integration` ověří stav. Jen pokud GET chybí a je ověřen původní stav, použij `put_method(restApiId=API, resourceId=..., httpMethod='GET', authorizationType='NONE', apiKeyRequired=True)` a `put_integration(..., httpMethod='GET', type='AWS_PROXY', integrationHttpMethod='POST', uri=stejná URI původního POST)`, potom `create_deployment(restApiId=API, stageName='v1')`. Před mutací snapshot a rezervace budgetu; po ní readback a vlastní rollback/concurrency ochrany. Žádná změna Lambda policy/IAM; chybějící oprávnění reportuj.
- Preflight musí před přidáním akceptovat absenci nové GET, po nasazení ji vyžadovat. Současný dict `routes` má dvakrát `/cases`, takže přepisuje POST: použij seznam dvojic a testuj všech pět metod. To je součást tohoto tasku, ne důvod skončit.
- HTTP runner rozšiř v `Transport.request`, `run`, `write_matrix` a `scenario`; sdíleně účtuj všechna HTTP volání ještě před odesláním. Reuse `api_key()` (tajný klíč jen v paměti), `expect()` a fixture manifest. Přidej globální stránkování/auth/token scénáře výše. Samotné spuštění staré sady globální cestu neověří.
- Tyto příkazy nejsou náhrada chybějící implementace: nejdřív ji dokonči. Chybějící kód v tomto scope je práce k provedení, ne externí blocker. Pokud narazíš na skutečnou bezpečnostní/autorizační překážku, uveď konkrétní operaci a sanitizovaný důvod; nepředstírej úspěch.

## Hranice
Pouze tento repo/component a existující Lambda wonderfulkb-case-client/API bgm7k1ggqi/v1, účet609394381050/eu-central-1, profil ai-hackathon. Bez změn IAM/tabulek, secretů v evidenci nebo nových klientů. Bezpečnost/rollback/semantika: `plans/checkpoints/case-client-list-all-live/authorized-contract-20261019.md`. Použij dosud NEČERPANÝ ledger `case-global-72fa-20261019-1909/manifest.json` ve stejném adresáři: 3forward+1rollback,60min od první mutace,12POST/200HTTP,≤2req/s/concurrency2. Čítače nikdy nenuluj; nejde o historických5/5. Pro syntetické klienty použij manifest `plans/checkpoints/case-client-live-integration/host-case-live-20261019-1820/manifest.json`. Běžná instalace/deploy jsou schválené; skutečné AccessDenied/expiry/konkurence zůstávají stop.

## Ověření
Doplň unit testy chybějících změn; implementuj TDD pomocí skill:tdd a důkaz předej v kořenovém `plans/checkpoints/` pro aktuální task. Zachovej všechny registrované brány. Live: globální limit1 traversal obsahuje cases dvou klientů bez duplicit/ztrát, cizí/poškozený token400, chybějící/neplatný klíč403; regresně původní čtyři operace včetně POST201→GET a metadata. Sanitizovaný report musí obsahovat výsledky, čerpání ledgeru, Gateway deployment a shodný Lambda hash před/po testech. Opravuj vnitroskopové chyby a opakuj v povolených limitech; hotovo je funkční nasazení, ne předání deploye hostiteli.
