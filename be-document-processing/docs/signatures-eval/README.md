# Textract SIGNATURES: úplnost a přesnost nálezu (19. 10. 2026)

Detektor `TextractSignatureDetector` (`src/document_processing/signatures.py`), Textract `SIGNATURES`, eu-central-1.
Výsledky dvou skupin se **nesčítají** a výsledek skupiny A se **nepřenáší** na rukopisné podpisy ve skupině B.

## Skupina A: 20 syntetických případů s generickými podpisy

- **Pravda:** `marks[].signature_bbox` v anotacích balíku `synteticke_dokumenty_20_pripadu.zip` (323 podpisů, 165 PDF, 489 stran). Pozice v PDF bodech, počátek vlevo nahoře.
- **Postup:** `scripts/eval_signatures.py` řeže každou stranu na jednostránkové PDF a posílá ho do `AnalyzeDocument(SIGNATURES)` jako bajty (nic se nezapisuje do AWS). Nález se páruje s pravdou 1:1 (IoU ≥ 0,2, nebo střed nálezu uvnitř pravdivého boxu rozšířeného o 10 %). Surové odpovědi Textractu jsou ve scratchpadu a ve výstupu skriptu, opakování nic nestojí.
- **Odlišnost od produkční cesty:** worker volá asynchronní `StartDocumentAnalysis` ze S3. Měření šlo přes synchronní volání se stejnou funkcí `SIGNATURES`; motor je stejný, cesta ne.

| | dokumentů | podpisů v pravdě | nalezeno | minuto | falešné nálezy | úplnost | přesnost |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Celkem** | 165 | 323 | 297 | 26 | 1 | **92,0 %** | **99,7 %** |
| A/B (vektorová PDF, 10 případů) | 80 | 185 | 166 | 19 | 0 | 89,7 % | 100 % |
| C (skeny a degradace, 10 případů) | 85 | 138 | 131 | 7 | 1 | 94,9 % | 99,2 % |

Dokumentů s nějakým podpisem je 129; **všechny** podpisy našlo Textract u 107 z nich (83 %). Podrobně po typu kvality: `groups.csv`, po dokumentech: `documents.csv`, každý minutý podpis: `missed.csv`.

- **Závěr „100 %" neplatí ani pro skupinu A.** Úplnost je 92 %.
- **Misses nejsou náhodné:** drží se konkrétního obrázku podpisu (`signature_identity`). Podpis `76afe6ee…` je minutý 6 z 9 krát, `a185b13e…` 3 z 49, `ca130e92…` 3 z 74. Nepřenášet na jiné podpisy.
- **Jediný falešný nález:** `SYN-C05/11_specifikace.pdf`, strana 1, `detection_score` 69. Neprověřoval jsem, co to je (razítko nebo obrázek).
- **Role (jen u nalezených, 287 hodnocených):** určena u 224 (78 %), z toho správně 190 (85 %) a **špatně 34 (15 %)**. Chyby jsou systematické: podpis objednatele dostane roli dodavatele (10), podpis pojistníka dostane roli pojistitele podle názvu pojišťovny v blízkosti (9 + 5), u příjemce financování se role někdy chytí z cizího sloupce. Role z blízkého textu je tedy orientační, ne pravda. V mapování z českých popisků anotace na naše role je rozhodnutí (např. „Pojistník" → borrower, „Objednatel" → buyer), které výsledek ovlivňuje.

## Skupina B: 2 původní případy s lidským rukopisem (`solom-rec`, `stavby-fiser`)

- **Pravda:** žádná anotace neexistuje. Počet podpisů jsem určil **ručně z vykreslených stran** (75 dpi, červeně nálezy Textractu). Prohlédnuto 40 stran: všechny strany s nálezem a všechny strany s popiskem „Podpis" a všechny strany dokumentů se skenovanou přílohou. Strany bez popisku a bez nálezu jsem neprohlížel, případné podpisy tam nebo parafy nejsou započítané. Moje počítání může mít chyby, hlavně u razítka s podpisem.
- **Postup:** produkční cesta (`StartDocumentAnalysis` ze S3 přes `scripts/detect_signatures.py`/detektor), 16 PDF, 74 stran.

| dokument | stran | podpisů (ručně) | nalezených boxů | poznámka |
|---|---:|---:|---:|---|
| solom-rec/01_Form_VOP | 19 | 3 | 1 | chybí „Kn." a „Jn." |
| solom-rec/09_Dohoda o zaplacení | 4 | 4 | 3 | jeden box pokrývá dva podpisy najednou |
| solom-rec/0_Form_Smlouva | 4 | 3 | 2 | chybí „Kn." |
| solom-rec/10_Podklady, objednávka | 2 | 3 | 1 | chybí modrý podpis „Vystavil" a razítko s podpisem |
| solom-rec/11_Podklady, protokol | 4 | 4 | 2 | chybí podpis technika a servisního střediska |
| solom-rec/2_Form_Zajišťovací převod | 6 | 3 | 3 | vše nalezeno |
| solom-rec/3_Form_Vinkulace | 2 | 2 | 2 | vše nalezeno |
| solom-rec/4_Form_Ručení | 3 | 3 | 2 | chybí „Kn." |
| solom-rec/99_KK_systAPI | 3 | 0 | 0 | |
| stavby-fiser/0_F_Smlouva | 4 | 3 | 1 | chybí „Kn." a „Jn." |
| stavby-fiser/10_Podklady, objednávka + TS | 9 | 3 | 2 | chybí „Kn." (objednatel) |
| stavby-fiser/11_Protokol | 2 | 1 | 1 | |
| stavby-fiser/14_Úhrada KC | 1 | 0 | 0 | |
| stavby-fiser/2_Form_Zajišťovací převod | 6 | 3 | 1 | chybí „Kn." a „Jn." |
| stavby-fiser/3_Form_Vinkulace | 2 | 2 | 1 | chybí „E" příjemce |
| stavby-fiser/99_KK_systAPI | 3 | 0 | 0 | |
| **Celkem** | 74 | **37** | **22** | |

- **Úplnost ≈ 59 % (22 z 37 boxů)**; započteme-li sloučený box jako dva podpisy, 23 z 37 (62 %). Pro rukopis je to výrazně horší než skupina A.
- **Falešné nálezy:** ve skupině B jsem žádný neviděl; každý box ležel na podpisu nebo na razítku s podpisem. Jde o malý vzorek.
- **Role u nálezů:** určena u 12 z 22; ve vykreslených stranách jsem u žádné neshledal chybu. Vzorek je příliš malý na srovnání se skupinou A (tam 15 % chyb).
- **Tendence:** nejčastěji minutý je rukopis „Kn." (podpis Jana Kováka), který se opakuje v obou případech.

## Doporučení

1. **Textract samotný nestačí.** Prázdný nález ani počet podpisů nelze brát jako důkaz, že podpis chybí. Pro rukopis minul zhruba 4 z 10 podpisů.
2. Jako druhý detektor navrhuju **ukotvení na popisek**: v OCR najít řádky „Podpis" / „razítko a podpis" / „Datum a podpis", vyříznout oblast nad nimi a zjistit, zda je tam inkoust (jednoduchá hustota tmavých pixelů, nebo vision LLM s otázkou ano/ne na výřez). Tvar dokumentů to umožňuje, protože podpisy stojí u popisku. **Neotestováno**, je to nápad, ne měření. Vision LLM nedává kalibrovanou jistotu.
3. Role neurčovat z nejbližšího textu pouze podle klíčových slov; potřebovala by sloupcovou geometrii tabulky podpisů (popisek strany nad sloupcem). Jinak ji považovat za návrh k ověření člověkem.
4. U bankovního použití zobrazit člověku výřez strany s boxy; počet podpisů nezávisle porovnávat s požadavkem dokumentu (kolik jich má být), ne s tím, kolik jich Textract našel.

## Náklady a reprodukce

Zhruba 570 stran Textractu (489 + 74 + několik zkušebních). Při orientační ceně 3,5 USD za 1000 stran asi 2 USD; cenu jsem neověřoval proti ceníku ani účtu.

```bash
cd be-document-processing
PYTHONPATH=src python scripts/eval_signatures.py ROOT --out DIR --dry-run   # počet stran a odhad ceny
PYTHONPATH=src python scripts/eval_signatures.py ROOT --out DIR             # měření (ROOT = rozbalený balík)
```
