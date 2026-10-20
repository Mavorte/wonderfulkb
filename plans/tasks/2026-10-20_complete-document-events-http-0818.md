---
title: "Monitoring HTTP: dokončit autentizovaný document-events základ a skutečné nasazení"
type: implementation
---
# Dokončit document events HTTP základ

## Skutečný nedodaný scope
Nahrazuje nedodaný task9d34c790, source route processing_monitor_routes.py vůbec není. Host review plans/checkpoints/acceptance-host-review-0818-read-reducer.md a původní blocker plans/monitoring/task-9d34c790-5c01-46ba-96d0-bc7f45740763-blocker.md. Sdílený x-api-key + existence case nejsou trusted identity→case authorization. Existující minimální test je jen sketch, ne implementation proof.
První technický bod plánu: doložit legitimní service-side identity→case authorization interface/owner a bezpečnou oprávněnou syntetickou fixture z reálných existujících technických kontraktů. Není povolení vymyslet JWT/cookie/auth framework, neověřené claims/header, broadIAM nebo obejít chybějící seam. Chybějící rozhodnutí pojmenuj přesně jako blocker; žádná exposed neautorizovaná route/deploy a žádný source-only fakecomplete. Toto se nevyřeší libovolným allow-all test doublem vydávaným za službu.
Jakmile konkrétní legitimní seam existuje, dodat přesně níže celé HTTP TDD/source/install/deploy/live ověření ve stejném tasku. Jediný OpenAPI pouze čti/ověř, nenahrazuj práci existujícího jediného kontrakt ownera ani nevytvářej druhý YAML. Přesně rozliš SOURCE/INSTALLED/DEPLOYED/LIVE_VERIFIED.

## Ověření, evidence a hranice
Použij projektový `be-document-processing/.venv/bin/python` z kořene repo; pytest zde načítá src přes conftest, pro přímé syntetické probe nastav explicitně `PYTHONPATH=be-document-processing/src`. Nepoužívej systémový python/python3 ani fallback, který způsobil původní nesémantický RED. Ověř závislosti před capture. Pracuj pod NOVÝM vlastním task ID, vlastní plans/checkpoints/<task-id>.red-green-proof.md; staré failed proof/history se nesmí přepisovat, mazat nebo vydávat za green. Genuine RED je požadovaná chybějící vlastnost, ne dependency/collection/environment chyba; stejná argv pro RED/GREEN. Načti skill:tdd a použij skutečně podporované rozhraní, ne čtení zakázaných helper internals nebo obcházení oprávnění. Capability denial je konkrétní blocker.
Spusť jednotlivé focused testy, celou příslušnou audit matici i plné `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests`, pak registrované `npm --prefix apps/backoffice test` a `npm --prefix apps/backoffice run build`. Nevyřazuj failing tests ani nesnižuj assertions, nevytvářej collection ignores; odliš unrelated blocker od vlastního výsledku. Testy kvality kontraktu nesmí slepě vyžadovat ValueError tam, kde Python odmítá chybějící/nepovolený argument TypeError; oprav očekávání pouze proti explicitní sémantice neplatného vstupu, ne pro zakrytí skutečné validace.
Pouze wonderfulkb a níže vymezené source/tests plus vlastní task plan/proof/learning. Žádná instrukční/config/platform/task lifecycle změna, nový runtime/dependency/framework ani přístup do jiných repo. Exact module names domain-qualified; žádné utils.py/common.py/state.py/runs.py. No live provider/queue/replay/inference/business writes. Jen HTTP slice níže zachovává své specifické standing test-deploy+live povolení a povinnosti; pure domain slices nic nenasazují. Zachovej ostatní rozpracované source a historické artefakty.

## Přesný původní scope včetně standing test deploymentu
# Monitoring MVP: jeden GET dokumentových událostí

## Goal
Ve stávajícím intake FastAPI číst FileReceived z jediného audit store. Jeden endpoint, žádná nová služba.

## Files/functions
Nový tenký `be-intake/app/processing_monitor_routes.py`, zapojení v existujícím main.py, interní `audit_queries.py`; jediný existující `be-document-processing/contracts/openapi-processing-monitor.yaml`. Vstup: `plans/monitoring/mvp-reference-20261019.md` a auditní write/read interface.

## Change
GET `/v1/cases/{case_id}/processing/documents/{document_id}/events`, list `items`, `next_token`, `observed_at`. Limit 1–100, document-partition Query a scope-bound token. Stabilní order occurred_at,event_id; refresh od začátku, bez incremental cursor/revision/fencing/late-event catch-up garance. Neúplnost fail-open historie přiznat, unknown není business failure.

Zachovat autentizaci, použít skutečný důvěryhodný case-authorizační seam. Sdílený API klíč, existence case nebo browser case header samy nejsou oprávnění. Pokud seam chybí, popsat konkrétní blocker; nepřidávat auth framework a nevystavit API bez něj. Čtení existence přes nynější case/document klíče, ne historický pk/sk adapter. Neexistující/cizí scope 404 nebo ověřená konzistentní 403 politika, nutný read failure 503, `Cache-Control: private, no-store` i na chybách. Žádné výjimky s obsahem dokumentu.

Existující YAML zúžit na API-only MVP, jediná nyní dodaná operace; ostatní budoucí návrh ponechat v guide, ne jako aktivní endpointy. Bez business list/detail a artifact-content API.

## Boundaries
Pouze wonderfulkb. Bez run endpointů/projekcí, UI, proxy, nového runtime nebo nesouvisejících live business writes. Packaging znovu nevymýšlet, jen zapojit router do zabaleného intake.

## Verification
Focused FastAPI testy: happy path s FileReceived, dvě stránky a cross-document token odmítnut, neautentizovaný a nepovolený case, neexistující document, chyba store→503. Ověřit no-store. Validace jediného YAML a registrované gates. Žádná rozsáhlá fault/TTL/refresh matice. Implement the TDD cycle using skill:tdd.

## Společné umístění API
Processing Monitor API je jediný router `be-intake/app/processing_monitor_routes.py` ve stávající službě `wonderfulkb-ingest` (Python/FastAPI, AWS App Runner, eu-central-1), na stejném hostu jako upload. Aktuální test host `https://vt9mavpjky.eu-central-1.awsapprunner.com` je provozní údaj, ne hardcoded default. První operace: `GET /v1/cases/{case_id}/processing/documents/{document_id}/events?limit=50`, pokračování parametrem `next_token`. JSON `items`, `next_token`, `observed_at`. Žádná nová služba, Lambda ani API Gateway; deployment tohoto read API a jeho live HTTP ověření jsou povinnou součástí tohoto tasku.

## Povinné dokončení: skutečné nasazení a dotažení read API
Výslovný požadavek Michala 20.10.2026: tento read přírůstek není hotový lokálním testem/buildem. Součástí TOHOTO zadání je provést instalaci/package build, skutečné in-place nasazení do EXISTUJÍCÍHO AWS test cíle a ověřit i doladit novou funkcionalitu přes skutečné HTTP. Neodkládat nasazení na závěrečný integrační task nebo samostatný smoke. Platí též pro rozšíření DTO/allowlistu již existujícího GET, nejen novou route.

1. Zkontrolovat aktuální skutečný cíl/owner a podporovaný build/deploy postup, source→image/package provenance a instalaci audit package v intake artifactu. Read API patří do existujícího `wonderfulkb-ingest` FastAPI/App Runner, eu-central-1; URL/credentials zjistit bezpečně ze stávající konfigurace, ne hardcoded default. Žádný nový server, Lambda/API Gateway, deployment framework nebo automatický merge/publikace. Nevymýšlet workflow, které repo nemá.
2. Agent tuto změnu dodá end-to-end včetně rutinního test deploymentu, pokud to umožňují jeho skutečná oprávnění a existující deployment rozhraní. Použít standing AWS test authorization v AGENTS.md, zachovat stávající env/IAM/auth a nesouvisející konfiguraci, před změnou uchovat ověřený recovery artifact/config, použít revision/concurrency guards a bounded čekání na skutečné dokončení rollout/health. Neukládat secrets do souborů evidence. Žádné produkční/nesouvisející resources, broad IAM změny či destruktivní data operace.
3. Po nasazení provést bounded autentizované HTTP ověření PŘÍMO změněné route/DTO na známém oprávněném syntetickém case/document: očekávaný JSON/scoping/filtr/nová observation, continuation kde relevantní, private,no-store a negativní auth/scope podle skutečné politiky; read failure→503 ověřit hermeticky bez cloud fault injection. Nepostačuje /health,200empty nebo lokální TestClient jako důkaz nové funkcionality. Zkontrolovat skutečnou image/revision/digest a čas operace, nikoli jen úspěšné odeslání deploy commandu.
4. Použít existující bezpečnou syntetickou cestu/fixture a nejmenší doložitelný počet writes; fixture ID/case/počet requests uvést v evidenci. Žádný replay reálných dokumentů, ambiguous non-idempotent opakování, ruční audit insert vydávaný za worker→HTTP, nová placená inference nebo zásah do queue/lease/retry jen pro smoke. Pokud nový producer ještě nedodává daný event, rozlišit nasazený GET od NEOVĚŘENÉ live obsahové větve; skutečně doložený dřívější syntetický event smí posloužit bez replay. Chybějící trusted auth/source/fixture nebo skutečný permission denial je konkrétní blocker, nikoli důvod předstírat success/complete.
5. Agent opraví ve stejném scope zjištěné implementační/package/router chyby, znovu lokálně ověří, guardovaně nasadí a opakuje omezený smoke do funkčního výsledku. Při outage/bezpečnostním riziku použít ověřený rollback, nepřepisovat současnou cizí revizi. Rozšíření business scope/permissions neprovádět.
6. Pokud repo-scoped runtime nemá podporované deploy oprávnění/rozhraní, nic neobcházet. Připravit konkrétní artifact digest, target, config diff, recovery a přesný zbývající krok pro Jackieho. Jackie provede úzký operator krok v rámci TÉHOŽ zadání podle standing authorization; agent stále doplní ověření a závěr, nejde o source-only DONE ani nový task odkládající deployment. Rozlišit výsledný stav SOURCE / INSTALLED / DEPLOYED / LIVE-FUNCTION-VERIFIED; úspěšná dodávka vyžaduje skutečný deployed+ověřený výsledek, jinak transparentní konkrétní blocker.

Výstup: repo-local evidence specifická pro tento task v `plans/monitoring/`, source/artifact digest a target revision, provedená instalace/deploy, safe HTTP status+ID/schema assertions a nalezené/doladěné chyby, případný rollback/konkrétní blocker. Bez dokumentového obsahu, credentials nebo smyšlené live evidence. Zachovat plán/review/acceptance i všechny registrované test gates; source/lokální green sám není runtime acceptance. Toto povolení nahrazuje staré zákazy test deploymentu/AWS smoke v rozsahu tohoto read přírůstku, NE ostatní bezpečnostní hranice.

## Jediný OpenAPI kontrakt – hranice vlastnictví
`be-document-processing/contracts/openapi-processing-monitor.yaml` je vstupní společný kontrakt, ne editovaný výstup tohoto řezu. Původní formulace žádající jeho úpravu/zúžení zde nahrazuje ověření konkrétní route/DTO vůči JEDINÉMU YAML a zachování ostatních specifikovaných operací; budoucí operace ve specifikaci nejsou tvrzení o nasazení. Případný rozpor dolož přesným path/schema, nevytvářej druhý kontrakt ani tichou změnu. Požadavek instalace, skutečného AWS test deploymentu, konkrétního live HTTP ověření a truthful blocker závěru se NEMĚNÍ; nejde o source-only dodávku.


## Doménové HTTP moduly – upřesnění vlastnictví
Document/run events a attempts tvoří společný HTTP základ. `processing_monitor_routes.py` zůstává kompoziční facade ve stávajícím intake; sdílená auth/document-scope/no-store/error a bounded-reader vazba má jednu implementaci. Reuse skutečný `read_document`/AuditStore interface; nepřidávej konkurenční reader/store. Run a attempts rozšíření mohou mít doménově kvalifikovaný modul `processing_monitor_event_routes.py`, bez druhé aplikace. Zachovej existující změny a ostatní připojené routes.
Tato sekce upřesňuje starší široký seznam Files/functions. Žádný nový server/proxy, generický framework, druhý reader, auth fallback nebo volný název routes.py/utils.py. Sdílený OpenAPI YAML pouze čti/ověř. Pokud nezbytný technický seam chybí, dolož konkrétní interface a blocker; neimplementuj fake úspěch. Zachovej veškeré TDD, review/acceptance/registrované gates a povinné nasazení + live ověření tohoto tasku.
