---
title: "Case & Client: jedna Lambda s explicitními mock daty, offline testy a minimálním SAM balením"
type: implementation
---

# Case & Client: jedna Lambda s explicitními mock daty, offline testy a minimálním SAM balením

## Cíl a vstupy

V repozitáři Wonderful KB dodat první nasaditelnou verzi `wonderfulkb-case-client`: existující čtyři API operace nad syntetickou in-memory repository, bez přístupu do databáze či AWS při testech. Referenční HTTP kontrakt je `be-case-client/openapi-case-client.yaml` (1.3.0-final). Aktuální scope určuje `docs/proposals/proposal-20261019-114433-08800d_case-client-lambda-vyvoj-nezavisly-na-externi-databazi.md`, části decisions/lambda-mock; starší `plans/case-client-aws.md` je pouze kontext, nikoli pokyn realizovat celou DynamoDB architekturu.

Výstup je lokálně ověřený kód a nasaditelná servisní SAM šablona s README. Skutečné nasazení a cloudový smoke provádí host mimo tento coding task.

## Rozsah a zvolená jednoduchost

- Jediné povolené zdrojové změny: `be-case-client/**`; frontend, jiné repozitáře, externí config a pipeline lifecycle nejsou součástí tasku. Dokumentaci komponenty lze doplnit. Zdrojové OpenAPI zachovat; popsat mock odchylky v README.
- Python 3.13 AWS runtime, standardní knihovna; nepotřebujeme web framework, boto3, ORM, Docker, DynamoDB Local ani lokální HTTP server. Testy přes `unittest` mají jít spustit podporovaným lokálním Pythonem bez nového cloudu.
- Jeden handler a úzké repository rozhraní přes konstruktor/factory, za něj později dosadíme reálnou DB. Žádný plugin framework, abstraktní vrstvy navíc, generátor nebo druhá aplikace.
- Použij doménová jména `case_client_handler.py`, `case_client_repository.py`, `case_client_mock_repository.py`, `test_case_client_lambda.py` a odpovídající samo-vysvětlující názvy dalších nutných souborů. Nepřidávej obecné `service.py`, `utils.py`, `storage.py`, `state.py`. Před přidáním zkontroluj duplicity těchto basename v tomto repozitáři.

## Implementace

1. Fixture JSON s několika syntetickými klienty (`active`, `inactive`, `blocked`), názvy s diakritikou/právní formou, klientem bez case a předem známými cases s různými časy. Správné UUID/IČO, žádné reálné osobní údaje. Každá nová repository dostane vlastní hlubokou kopii fixtures.
2. Explicitní režim `DATA_BACKEND=mock` + `ALLOW_EPHEMERAL_MOCK=true`; obě hodnoty nastaví SAM. Chybějící/nesprávný režim nesmí automaticky aktivovat mock. Žádný AWS SDK ani credentials lookup. V odpovědích handleru hlavička `X-Data-Backend: mock`.
3. Handler přijímá API Gateway REST proxy eventy, vrací `statusCode`, JSON `body`, JSON content-type. Implementovat existující routy:
   - `GET /clients`: AND filtr IČO/název/status, normalizace velikosti písmen/diakritiky/běžných právních forem jako celých výrazů; limit 1–100/default50, bezpečně validovaný neprůhledný token navázaný na dotaz. Nevracet interní normalizované atributy.
   - `POST /cases`: validovat JSON, case ID a UUID; nový aktivní klient → 201/status open/UTC created_at. U stejného ID a klienta vrátit původní case 200, neměnit metadata ani čas. Jiný klient ke stejnému ID →409. Nový neexistující klient →404, inactive/blocked→409. Existující stejné ID+klient ověřit před kontrolou jeho aktuálního stavu.
   - `GET /cases/{case_id}`: známý fixture či v této repository vytvořený case →200, jinak404.
   - `GET /clients/{client_id}/cases`: nejprve existence klienta, jinak404; existující bez case má prázdný seznam; nejnovější první, filtr status, validované stránkování.
   - Chyby mají tvar `{"error":"..."}`. Základní validace podle OpenAPI; pro mock stanovit ochranný limit metadata16KiB UTF-8 JSON, dokumentovat ho jako demo omezení. Neplatný JSON/filter/token→400. Provozní/config chyby nesmějí předstírat úspěšný prázdný seznam.
4. Stav vytvořených cases držet pouze v paměti daného execution environmentu; nevytvářet soubory do /tmp ani externí úložiště. Uvnitř repository zajistit konzistentní rozhodnutí create/repeat/conflict. **Neslibovat trvalou nebo globální idempotenci:** při cold startu se stav resetuje, jiné instance mají jiná data. Mock musí být v README i konfiguraci nezaměnitelný s produkční DB.
5. Jedna minimální `template.yaml`: `AWS::Serverless::Function` s Python3.13/CodeUri zdrojové složky, jedna `AWS::Serverless::Api` typu REST, stage `v1`, čtyři proxy routy, API key required, jeden klíč/usage plan a vazba na stage, JSON gateway 403/429. Malá on-demand Lambda (256MB/10s) a krátká log retention. Role pouze pro nutné logy, bez DB/S3/VPC práv. U tagovatelných prostředků `project=wonderfulkb`. Výstupy URL a nesekretní identifikátory; nehodnotu API klíče. Nevytvářet custom resources, tabulky, stacky pro další služby nebo CI/CD.
6. README obsahuje přesné offline příkazy, přímé testovací eventy a krátký host runbook pro `sam validate --lint` a `sam deploy --guided --profile ai-hackathon --region eu-central-1 --stack-name wonderfulkb-case-client-mock` s nutným IAM acknowledgement. Protože kód nemá dependencies, použít přímé CodeUri balení bez povinného container buildu; případný nativní `sam build` vysvětlit jen pokud jej skutečně používá zvolený runbook. Nestanovovat SAM/Docker jako podmínku unit testů. Popsat bezpečné získání klíče mimo soubory/output repozitáře, URL, smoke a úklid pouze vytvořeného mock stacku.

## Smoke scénář v README (neprovádět v tomto tasku)

S platným klíčem seznam klientů, detail známého **zabaleného fixture case**, seznam cases; nový POST→201; fixture neaktivního klienta→409 a neexistujícího→404. Bez klíče/nesprávný klíč→403. Marker mock ověřit na úspěšných Lambda odpovědích. Neověřovat persistenci pomocí POST→další GET ani opakovaný HTTP POST→200: mezi instancemi tato záruka neexistuje. Idempotence se prokazuje offline nad jednou repository. API key se nesmí logovat nebo přidat do výstupní dokumentace.

## Testy a acceptance

- Testy volají **skutečný handler se skutečným mock adaptérem**, ne izolované mocky obou stran. Pokrýt všechny čtyři routy, výše uvedené response tvary/validace, filtr AND, normalizaci, řazení a stránkování včetně chybného/cizího tokenu, 201→200 ve stejné repository, 409 jiné vlastnictví, chybějícího a neaktivního klienta, veřejnou serializaci a reset v nové repository.
- Ověřit nepřítomnost AWS credential/síťových volání, chybu neexplicitního režimu a mock hlavičku. Testy si samy nastavují konfiguraci; nepotřebují reálný API key nebo přihlášení.
- Přidat malou statickou kontrolu, že servisní šablona nezavádí databázové resources/práva a obsahuje zvolené čtyři routy s API key ochranou. Skutečnou gateway ochranu neoznačovat jako runtime-ověřenou.
- Očekávaná offline brána: `python3 -m unittest discover -s be-case-client/tests -p 'test_*.py' -v` a `python3 -m compileall -q be-case-client/src`. Uvést příkazy pro import path tak, aby přesně fungovaly z kořene repozitáře bez implicitního globálního PYTHONPATH.
- Zachovat a ověřit existující `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build`.
- `sam validate --lint`, pokud je SAM dostupný; pokud chybí, uvést přesný chybějící nástroj pro hosta a neprohlásit validaci/deploy za úspěšné. Host před nasazením validaci skutečně provede a rozšíří registrovanou projektovou bránu o backendové testy bez odstranění frontendu. Worker nečte/nepřepisuje externí registry/config.
- Finální poznámka: změněné soubory, skutečné příkazy/výsledky, případné named blockers, omezení mock persistence a jednoznačně oddělené lokální ověření od neprovedeného AWS deploye.

## Bezpečnostní hranice

Žádné AWS API operace, provider/model/message volání, deploy, databázové připojení/seed, lokální modely, změny služeb/schedulerů, credentials nebo externí konfigurace. Nepřidávat autocommit. Žádné čtení jiných repozitářů a žádná správa task lifecycle. Účelem je malá hotová mock služba, nikoli implementace druhé DB fáze nebo infrastruktury navíc.
