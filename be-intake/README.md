# Ingest API (`wonderfulkb-ingest`): nahrávání dokumentů, pro Wonderful

Stav: **služba běží na App Runner; adresu a API klíč dostanete od nás.** Formální popis: [openapi-ingest.yaml](openapi-ingest.yaml). Navazuje na [Case & Client API](../be-case-client/openapi-case-client.yaml): case musí existovat (zakládá se přes `POST /cases`).

- Base URL: `<UPLOAD_URL>` (tvar `https://<id>.<region>.awsapprunner.com/v1`, všechny cesty níže jsou pod `/v1`). **Je to jiná adresa než u Case & Client API.** Upload běží jako samostatný kontejner, protože API Gateway a Lambda by 4–5 MB soubory nezvládly s rezervou.
- Autentizace: hlavička `x-api-key: <klíč>` u každého volání pod `/v1`. **Klíč je jiný než u Case & Client API** (to má vlastní klíč z usage plánu `wonderfulkb-demo-plan` v API Gateway); se stejným klíčem jako ingest se volá Validator Agent API. Klíč kontroluje sama služba, ne API Gateway. Klíč nikam nezapisujte do repozitáře ani do kódu prohlížeče, volejte ho z backendu.
- Kontrola dostupnosti: `GET /healthz` (bez `/v1`, bez klíče) vrací `200 {"status": "ok"}`.
- Formát: nahrání je `multipart/form-data`, ostatní odpovědi jsou JSON (UTF-8), časy v ISO 8601 (UTC).
- Chyby: `{"error": "popis"}` s kódem 400 (špatný požadavek, např. chybí `files`, neplatné `case_id`, parametr mimo rozsah), 401 (chybí klíč), 403 (špatný klíč), 404 (case neexistuje), 413 (moc velké), 415 (není PDF), 5xx (zkuste znovu). Kód 429 tu není, služba nemá usage plán. Klíč se kontroluje před čtením těla, takže bez platného klíče se nic nenahraje.
- Limity: až 20 souborů na volání, 25 MB na soubor, 100 MB všech souborů dohromady v jednom požadavku.

## 1. Nahrání dokumentů
`POST /cases/{case_id}/documents`, `Content-Type: multipart/form-data`

| Pole | Povinné | Popis |
|---|---|---|
| `files` | ano | PDF. Pole se opakuje, jedna část na soubor. `filename` části je původní název souboru. |
| `uploaded_by` | ne | Kdo dokumenty nahrál (do auditu), max 255 znaků, např. `reviewer@kb.cz`. |

```bash
curl -X POST "$UPLOAD_URL/cases/170170-25/documents" -H "x-api-key: $API_KEY" \
  -F uploaded_by=reviewer@kb.cz \
  -F files=@0_Form_Smlouva.pdf \
  -F files=@01_Form_VOP.pdf
```
Odpověď `201 Created`:
```json
{ "case_id": "170170-25",
  "documents": [
    { "document_id": "7d0c5f1e-3a52-5c0e-9b3c-1f6a8e2d4b90", "filename": "0_Form_Smlouva.pdf",
      "received_at": "2026-10-19T14:15:00Z", "content_type": "application/pdf",
      "size_bytes": 412331, "duplicate": false } ] }
```
- **`document_id`** je zároveň `blob_id`. Počítá se z `case_id` a SHA-256 obsahu, takže stejný soubor ve stejném case má vždy stejné `document_id`. Hodnoty v příkladech jsou jen ilustrace.
- **Duplicity:** stejný obsah v témže case se znovu nezapíše, vrátí se původní `document_id` a `duplicate: true`. Opakování volání je tedy bezpečné.
- **Všechno, nebo nic:** nejdřív se zkontrolují všechny části. Je-li jedna špatná (neplatný typ, moc velká), nezapíše se žádná a odpověď je chyba. Záznamy nových dokumentů se pak zapisují jednou transakcí, takže case uvidí všechny nově nahrané dokumenty, nebo žádný. Skončí-li volání chybou 5xx, zopakujte ho beze změny; stejné soubory se nezdvojí. Stejný soubor dvakrát v jednom volání se uloží jednou, druhý výskyt má `duplicate: true`.
- **Typ:** jen PDF, skeny také. Kontroluje se hlavička souboru `%PDF-`, ne jen `Content-Type` části. Jiný typ vrátí `415`.
- `404`: `case_id` neexistuje (zjistí se hned, před čtením těla, takže špatné volání nestojí celý upload). `413`: soubor je větší než 25 MB nebo součet souborů přesahuje 100 MB (je-li v požadavku `Content-Length` o víc než 1 MB nad 100 MB, služba ho odmítne hned, bez čtení těla). `400`: chybí `files`, je jich víc než 20, `uploaded_by` má přes 255 znaků nebo je neplatné `case_id` (1 až 128 znaků `A-Z a-z 0-9 . _ -`, ne samotné `.` nebo `..`). `415`: soubor nezačíná `%PDF-`, tedy i prázdný soubor.
- Soubory se ukládají do dočasného souboru a odtud streamují do S3, nedrží se celé v paměti. Request timeout App Runneru je asi 120 s, velké nahrání musí v tomto čase doběhnout.
- Odpověď obsahuje u každého dokumentu `duplicate`; `uploaded_by` se v odpovědi na nahrání nevrací, vrací se až ve výpisu.

## 2. Výpis dokumentů case
`GET /cases/{case_id}/documents?limit=50&next_token=…&with_urls=true`

Všechny parametry jsou volitelné. Řazeno podle času přijetí (`received_at`, vzestupně). `limit` je výchozí 50, 1 až 100 (jinak `400`). `next_token` je v odpovědi vždy, při poslední stránce `null`; jinak ho pošlete beze změny v dalším volání pro další stránku (je to zakódovaný offset, berte ho jako neprůhlivou hodnotu; neplatný token vrátí `400`). `with_urls=true` přidá ke každému dokumentu `download_url`, předpodepsaný odkaz platný 5 minut (300 s). `uploaded_by` je v dokumentu jen tehdy, byl-li zadán. Case bez dokumentů vrací `200` s prázdným polem.
```json
{ "case_id": "170170-25",
  "documents": [
    { "document_id": "7d0c5f1e-3a52-5c0e-9b3c-1f6a8e2d4b90", "filename": "0_Form_Smlouva.pdf",
      "received_at": "2026-10-19T14:15:00Z", "content_type": "application/pdf",
      "size_bytes": 412331, "uploaded_by": "reviewer@kb.cz",
      "download_url": "https://…" } ],
  "next_token": null }
```
`download_url` nikam neukládejte, po 5 minutách přestane platit. Další odkaz získáte novým voláním s `with_urls=true`.

## Doporučený postup
1. Založit case (Case & Client API, `POST /cases`) a zapamatovat si `case_id`.
2. Nahrát všechna PDF případu jedním voláním `POST /cases/{case_id}/documents`.
3. Při chybě sítě nebo 5xx zopakovat stejné volání, duplicity se nezapíšou dvakrát.
4. Nahrané dokumenty zobrazit uživateli přes `GET /cases/{case_id}/documents`.

## Co zatím neplatí
- Adresu a klíč vám předáme my, nejsou součástí repozitáře ani dokumentace.
- Mazání dokumentů a stav jejich zpracování přijdou později.
