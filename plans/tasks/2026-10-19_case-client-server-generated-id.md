---
title: "Case Client: sjednotit serverové UUID case s DynamoDB adaptérem"
type: implementation
---

# Case Client: sjednotit serverové UUID case s DynamoDB adaptérem

## Doložený rozpor
Michal 19.10.2026 požádal o kontrolu, zda novější změna nepovinného case ID nebyla ztracena. Host ověřil lokální8d45a14: handler vyžaduje case_id, POST pouze s platným client_id vrací400, POST s case_id vrací201. V novější samostatné vzdálené větvi feat-be-intake je commit177cc8f590f182e6b6971dcd53d15a5e584cb172: server generuje UUIDv4, dodané case_id ignoruje, každý POST zakládá nový case a vrací201 (žádná veřejná idempotence200). Dokumentační0e2b5e0acc7b51635df2e021460d57e7bf5323c0 ve větvi fix-docs-discrepancies potvrzuje stejnou změnu a OpenAPI1.4.0. Tyto změny nejsou součástí současné adapter větve; nejde o důkaz jejich přepsání. Předchozí ruční přejímka ověřila starý1.3.0-final kontrakt a tento novější rozdíl nezachytila.

## Aktuální remote podklady — požadavek Michala 19.10.2026 15:31
Host synchronizoval všechny remote refs a čistě integroval origin/main02774ce a origin/fix-docs-discrepancies0e2b5e0 do současné feature větve. Aktuální origin/feat-be-intake88c04ee6e850c147ffeba46fe626bb0acd4863f3 obsahuje navíc serverové UUID a dokumentaci; obsahový merge má konflikty v README, OpenAPI, handleru, mocku a Lambda testech. Neřešit jednostranným nahrazením adaptéru nebo novějšího kontraktu.

Všech28incoming souborů je materializováno jako lokální read-only reference v plans/handoffs/case-client-remote-20261019/ se SHA256 manifest.json a přesným sourceCommit. Sjednoť jejich změny se současnými soubory normálními editacemi; zahrň i nekolizní doprovodné README a docs/quick-connect.md. To rozšiřuje dokumentační scope na přesně manifestem vyjmenované README/docs/plans cesty; jiný aplikační kód mimo be-case-client neměnit. Snapshoty nejsou runtime modul ani druhá implementace, neupravovat je. Poslední quick-connect upozornění říká, že deployed POST stále vyžaduje ID: nejde o důkaz nasazení nového kontraktu. Zachovej rozšíření CaseDetails ze současné1.4.0 dokumentace, nevracej celý YAML na chudší incoming variantu. Výsledkem je obsahová integrace remote podkladů; host vlastní integraci historie.

## Výsledek a hranice
Sjednotit jedinou existující Python komponentu be-case-client se serverem přidělovaným ID a zachovat skutečný DynamoDB adaptér, mock, validace, Decimal serializaci, fail-closed konfiguraci a bezpečné transakční ověření aktivního klienta. Nedodat pouze mockovou změnu. Veřejná POST cesta nesmí zachovat starý replay200/owner-conflict kontrakt pro caller ID. Interní bezpečný conditional insert musí chránit před přepsáním při případné kolizi generátoru; kolize není oprávnění vrátit cizí case nebo jej přepsat. Přesnou strategii omezené kolize navrhnout v reviewed plánu.

Pouze zdroje/testy/dokumentace be-case-client/**, výše přesně povolená incoming dokumentace a repo-local plány/důkazy. Žádná frontend změna, jiný repozitář, globální config, credentials nebo cloud. Žádný deploy/AWS/HTTP/live test ani automatický post-deploy hook. Novější CaseDetails rozšíření dokumentace není samo o sobě zadání dalšího feature; zaznamenat oddělenou nejasnost místo tichého rozšíření scope.

## Přejímka
- Chybějící case_id s platným aktivním client_id →201, validní server UUIDv4; stejné dvě POST žádosti →dvě odlišná ID/201.
- Explicitně dodané case_id se ignoruje podle novějšího kontraktu (není jen náhradní fallback při chybění); i při opakování stejného dodaného ID vznikají nové UUID.
- Skutečný handler propojený s mockem i DynamoDB nad botocore Stubber; přesné SDK požadavky, UUID uložené/vrácené, následný strong get, podmíněný insert a řízená simulovaná kolize bez přepsání.
- Neaktivní/blocked klient409, neexistující404 a neplatné client_id/metadata400 zachovány. DB testy bez sítě/credentials, socket/DNS blokované.
- Aktualizovat OpenAPI, event, README a staré testy tak, aby skutečně testovaly nový kontrakt, ne pouze odstranily failing assertions. Zachovat ostatní coverage, SAM least-privilege a veřejné GET ID čtení.
- Celá unittest sada na Python3.13, compileall, SAM lint, existující registrované brány. Frontend toolchain chyby reportovat, neobcházet. Sanitizované přesné důkazy a nezávislá přejímka; žádné tvrzení runtime úspěchu.

## Závěrečná hranice
Pouze zdrojová integrace a lokální důkazy. Žádné AWS/HTTP/deploy ani task lifecycle operace.
