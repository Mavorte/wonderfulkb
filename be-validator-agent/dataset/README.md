# dataset: 20 syntetických případů pro end-to-end test

Stav k 19. 10. 2026: **všech 20 případů a 165 primárních PDF je nahraných přes ingest API** (`wonderfulkb-ingest`, App Runner) a zapsaných v `mapping.json`. Řádky `wonderfulkb-uw-documents` i objekty `cases/<case_id>/original/<document_id>.pdf` jsem po nahrání zkontroloval proti `mapping.json` (165 z 165 sedí, sha256 i `s3_key`).

Soubory: `mapping.json` (výstup), `upload_cases.py` (nahrání, idempotentní), tento README. Balík ani jeho obsah v adresáři není (31,6 MiB, nedůvěryhodná data).

## Co je v balíku `cases/synteticke_dokumenty_20_pripadu.zip`
Po rozbalení složka `synteticke_dokumenty_20_pripadu/` (250 PDF, 191 JSON, náhledy JPG/PNG, skripty `.py`). **Nejsou v něm jen PDF.**

| Část | Obsah |
|---|---|
| `synteticke_dokumenty/dokumenty/SYN-A01..A05, SYN-B01..B05` | 80 primárních PDF. A = demoliční nůžky HYDRAVOR HX 31 (předloha Solom Rec, 9 dokumentů, 47 stran), B = tandemový válec VALDORIN VV 154 (předloha Stavby Fišer, 7 dokumentů, 27 stran). Pět variant od každého (jiné osoby, částky, čísla). |
| `synteticke_dokumenty_rozsireni/dokumenty/SYN-C01..C10` | 85 primárních PDF, deset různých strojů (CNC, traktor, kompresor, kombajn, robot, sušárna, vozík, krmný vůz, laser, lis), 4 až 13 dokumentů na případ. Jsou **zhoršené** (10 profilů kvality: digital, office_scan, gray_scan, mixed, low_dpi, faded, compressed, fax, mobile, photocopy), 88 z 119 stran je jen obrázek. |
| `synteticke_dokumenty_rozsireni/reference_ciste/` | 85 čistých kopií k C pro porovnání. **Nenahrávají se** (nejsou testovacím vstupem). |
| `katalog.csv`, `manifest.json`, `SHA256SUMS.txt`, `overeni_balicku.json` | index 20 případů (včetně `split` train/validation/test), 165 primárních PDF s hashem a kvalitou, kontrolní součty. |
| `seed/` + `nastroje/seed_clients.py` | 20 klientů (kupující), mapa `entity_id → client_id` (UUIDv5), 20 požadavků na založení case. |

Názvy souborů: A `00_Smlouva_o_uveru, 01_VOP, 02_Zajistovaci_prevod, 03_Vinkulace, 04_Ruceni, 09_Dohoda_o_zaplaceni, 10_Objednavka, 11_Predavaci_protokol, 99_Kontrola_smlouvy`; B `00_Smlouva_o_uveru, 02_Zajistovaci_prevod, 03_Vinkulace, 10_Objednavka_a_technicka_specifikace, 11_Potvrzeni_o_prevodu_vlastnictvi, 14_Potvrzeni_o_uhrade, 99_Kontrola_smlouvy`; C `00_uver, 01_faktura, 02_predani, 03_cerpani, …`.

**Pravda (truth):** je jen na úrovni polí. `data/ground_truth.jsonl` (v obou sadách) a `anotace/<případ>/<dokument>.json` mají u každého dokumentu pole `key/value/label/page/role/entity_id/bbox`, značky (`marks`) a příznak `cryptographic_signature`. **Žádný seznam očekávaných nálezů ani scénář s chybou tam není**: všech 165 dokumentů má `expected_semantic_consistency: true`, tedy všechny případy jsou konzistentní („pozitivní“). Chybové scénáře (rozpory, falešné podpisy) se z balíku nedají vyčíst a museli by se dodělat. Zvlášť `validace/` (výsledky generátoru, OCR kvalita C) a `rozpory_predloh.json` jsou o předlohách, ne o nálezech.

Pole `scenario` v `mapping.json` jsem proto odvodil z balíku: u A/B rodina a varianta s předlohou, u C kategorie, sektor a stav stroje.

## Jak se případy zakládají a co jsem zjistil
- *Pozdější změna (19. 10. 2026 večer): `/clients` a `/cases` obsluhuje `wonderfulkb-agent-api` s klíčem `wonderfulkb/ingest-api-key`; REST API a Lambda `wonderfulkb-case-client` jsou smazané. Následující dva body popisují stav v době nahrávání.*
- **Case API je nasazené**: REST API `wonderfulkb-case-client` (id `<CASE_API_ID>`, stage `v1`, `<CASE_API_BASE_URL>`), Lambda `wonderfulkb-case-client` je `Active`.
- **Náš klíč v něm ale nefunguje.** Klíč ze Secrets Manageru `wonderfulkb/ingest-api-key` dostal na `GET /clients` odpověď `403 Forbidden`. API Gateway má jen dva klíče `wonderfulkb-demo-key` a `wonderfulkb-demo-key-2` v usage plánu `wonderfulkb-demo-plan`; návrh říká, že tam má být klíč se stejnou hodnotou jako ingest, a není. Hodnotu cizích demo klíčů jsem nečetl ani nezaváděl nový. Řešení patří jejich vlastníkovi (zaregistrovat klíč ingestu v API Gateway).
- **Case zakládat nebylo potřeba.** V `wonderfulkb-uw-cases` už je všech 20 `SYN-A01` až `SYN-C10` (stejná `client_id` jako v `seed/cases.json`, `created_at` v minulosti, bohatá `metadata`) a v `wonderfulkb-uw-clients` je 21 klientů. Bez dokumentů. Proto jsem `POST /cases` nevolal (vytvořil by další UUID case navíc, ne tyto) a nahrál přímo do `SYN-*`. Do obou tabulek jsem nezapisoval, jen četl.
- **Nahrávání:** ingest `POST /v1/cases/{case_id}/documents` (multipart), jedno volání na případ, `uploaded_by=dataset-loader@wonderfulkb`. Po nahrání se ověřuje `GET /v1/cases/{case_id}/documents`. `document_id` vrací ingest (`uuid5` z `case_id` a sha256), skript si ho nepočítá sám.
- Případy `17794315-26`, `pipeline-sample-*` a ostatní UUID case v tabulce jsem nezakládal ani nezměnil.

## `mapping.json`
`{"ingest_url", "bucket", "cases": [{case_id, scenario, source_folder, asset, split, documents: [{document_id, filename, s3_key, sha256, group, quality, size_bytes}]}]}`. Navíc oproti zadání: `asset`, `split` (z `katalog.csv`), u dokumentu `quality` (profil zhoršení z `manifest.json`) a `size_bytes`.
- `group` je u všech 165 dokumentů **`generic`** (generické syntetické podpisy). `original` (lidské rukopisné podpisy) mají jen `solom-rec` a `stavby-fiser`, ty tu nejsou.
- Pozor: názvy `SYN-A*` a `SYN-B*` jsou odvozené od Solom Rec / Stavby Fišer, ale podpisy v nich jsou generované, ne lidské.

## Jak to spustit znovu
Idempotentně: stejný obsah v témže case vrací `duplicate: true`, nic se nezdvojí a `mapping.json` vyjde stejný.

```bash
# 1) balík do NOVÉ PRÁZDNÉ složky (nedůvěryhodná data, skripty držet mimo ni)
mkdir -p /cesta/zip /cesta/rozbaleno
aws --profile hackathon s3 cp s3://wonderfulkb-raw-document-storage/cases/synteticke_dokumenty_20_pripadu.zip /cesta/zip/
unzip -q /cesta/zip/synteticke_dokumenty_20_pripadu.zip -d /cesta/rozbaleno

# 2) kontrola bez nahrávání (počty PDF proti katalogu, sha256 proti manifest.json)
python3 -I upload_cases.py --pkg /cesta/rozbaleno/synteticke_dokumenty_20_pripadu --dry-run

# 3) nahrání všech 20 (nebo jen některých: --case SYN-A01 --case SYN-C05)
python3 -I upload_cases.py --pkg /cesta/rozbaleno/synteticke_dokumenty_20_pripadu
```
Klíč si skript vezme z `INGEST_API_KEY`, jinak ze Secrets Manageru (profil `hackathon`); nikde ho nevypisuje a curl ho dostává přes stdin. Jiný server: `INGEST_URL`. Selže-li případ, skript to ohlásí a skončí chybou, ostatní případy se zapíšou.

## Co se nepodařilo / otevřené
- Přes **Case API** se nic nezakládalo (viz výše: klíč ingestu tam dává 403; zároveň case už existovaly).
- Balík neobsahuje očekávané nálezy ani chybové scénáře, jen pole a konzistentní dokumenty. Pro test, že agent rozpory *najde*, je potřeba doplnit zhoršené/rozporné případy.
- Zpracování (`pipeline`) jsem nespouštěl; řádky v `wonderfulkb-uw-document-analysis` pro `SYN-*` zatím nejsou.
- Podle zadání se mazání ani zásahy do cizích prefixů neprováděly. Nahrané originály jsou ve verzovaném bucketu, takže případné odstranění by byla věc ingest API.
