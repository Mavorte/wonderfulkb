---
title: "Case Client: GET /cases napříč všemi klienty"
type: implementation
---
# Case Client: GET /cases napříč všemi klienty

## Cíl
Přidat globální GET /cases do existujícího be-case-client a ověřit ho po nasazení na schválené testovací API. Žádná nová služba ani infrastruktura.

## Soubory
`be-case-client/src/case_client_{handler,repository,mock_repository,dynamodb_repository}.py`, související existující testy, `openapi-case-client.yaml`, `template.yaml`, README. Pro nasazení a HTTP ověření rozšířit existující komponentové nástroje dodané předchozí implementací; nevytvářet druhé.

## Změna
GET /cases vrací200 `{cases: [veřejné Case objekty], next_token: string|null}` bez povinného client_id. Prázdný seznam není404; zahrnout cases všech klientů bez lookupu klienta. Limit default50, rozsah1–100; žádné nové filtry ani garantované globální pořadí.

V obou repositories přidat list_cases. V DynamoDB použít stránkovaný Scan cases tabulky, nikoli klientský GSI. Znovupoužít současné fingerprint/cursor a budget mechanismy: globální cesta má vlastní identitu a case_id cursor; nesmí vstoupit do klientského lookupu/query. Zachovat správné pokračování i uvnitř SDK stránky, veřejnou projekci a sanitizované chyby. Vadný/cizí token→400.

## Hranice
Zachovat dosavadní čtyři operace, POST se serverovým UUIDv4 a schéma CaseDetails. Bez změny DB schématu/indexů/IAM, nového frameworku nebo full-table sortu. Nová routa má stejnou API-key ochranu.

Výslovně schválený deploy→HTTP test→opravy zůstává součástí výsledku. Jeho závazný rozsah a bezpečnostní limity jsou beze změny v `plans/checkpoints/case-client-list-all-live/authorized-contract-20261019.md`, pouze sekce **Výslovně autorizovaný deploy a live integrační cyklus** včetně podsekcí. Předchozí implementační/testovací rozpis v tomto archivu je historický, nikoli další zadání. Plánování read-only; běžné review a přejímkové brány zachovat.

## Ověření
Handler+mock a handler+Stubber: dva klienti→společný seznam; prázdná tabulka; limit1 a pokračování bez ztrát/duplicit; cizí token400; žádné čtení klientů. Zachovat regresní testy původních operací. Z kořene: `PYTHONPATH=be-case-client/src python3 -m unittest discover -s be-case-client/tests -p 'test_*.py'`. Implement the TDD cycle using skill:tdd.

Existujícím HTTP runnerem prokázat globální syntetické fixtures, stránkování, ochranu klíčem a regresi původních operací na nové nasazené verzi. Uchovat sanitizovaný report a ověřený deployment hash; lokální green nenahrazuje live výsledek. Plné registrované gates provádí pipeline.
