# Úplnost zamaskování podpisů: měření (19. 10. 2026)

Měřeno lokálně, bez zásahu do AWS dat (jen čtení z S3 a volání Textractu `AnalyzeDocument` s funkcí SIGNATURES). PDF jsou stažena do nové prázdné složky mimo repozitář; skripty a postup: [README.md](README.md). Kód redakce je beze změny (`signature_privacy.redact`); varianty zón jsou jen v `measure/zones.py`.

## Shrnutí

1. **Stávající konzervativní zóny (`v1`) samy nestačí.** Zóna se zakládá na popisku „podpis“, ale generické dokumenty tento popisek pod podpisem nemají (pod podpisem je tištěné jméno a funkce, nad ním hlavička role). Bez detektoru zamaskovaly zóny `v1` jen **4,6 %** pravdivých podpisů skupiny A (15 z 323). Skeny nemají textovou vrstvu, takže tam zóny nevzniknou vůbec.
2. **Stávající knihovna s výchozím řetězcem detekce pipeline (Textract + vložené obrázky + inkoust nad popiskem + lokální zálohy) skryla 98,8 % podpisů skupiny A** (319 z 323, interval 96,9 až 99,5 %). Čtyři podpisy zůstaly čitelné, všechny na skenech, kde Textract podpis nenašel a zóna nevznikla. U skupiny B (rukopis, ruční prohlídka všech 15 stran s podpisy) zůstaly čitelné **2 podpisy ze 37** (dva rukopisné podpisy na dvou stranách skenu `11_Podklady k výplatě _ Protokol`).
3. **Zóny `v2` (navržené tady) s detekcí skryly 323 ze 323 podpisů skupiny A (interval 98,8 až 100 %) a 37 ze 37 u skupiny B** (u jednoho podpisu zůstal nečitelný ocas tahu). Cena: zóny jsou větší (průměrně 17 % plochy strany u digitálních, 24 % u skenů); u digitálních PDF zóna maže jen kresby a vložené obrázky (text zůstává, změna vykreslení mimo oblasti do 0,5 % pixelů), u **skenů ale přepíše pixely včetně tištěného textu v zóně**.
4. **Zóny `v2` jsou laděné na týchž datech, na kterých se měří** (rozložení podpisového bloku syntetických dokumentů, k tomu skupina B z 16 PDF, kde `v2` zachránila dva podpisy). 100 % tedy není odhad pro cizí dokumenty, jen důkaz, že na těchto datech jde o 100 % dosáhnout. Doporučení v části 6.
5. **Našla se chyba ve `verify_redacted`** (falešné poplachy): hlásí „text v oblasti full“ u slov, která oblast jen škrtnou (dolní 0,3 b. tištěného jména těsně pod podpisem). **U stávající knihovny (`pipeline` `v1`) selhalo přísné ověření u 24 ze 181 dokumentů (13 %), u `v2` u 25**; pipeline by takový dokument ukončila jako `REDACTION_VERIFY_FAILED` a nic by nezapsala. Všech 24 případů jsou okrajové úlomky slov, nic jiného. Obálka `verify_tolerant.py` ponechá chybu jen u slov, která leží v oblasti z ≥ 30 % plochy; po ní zbývá u `v1` 0 a u `v2` 1 dokument. **Pozor, neshoda neodstraněná:** dry-run `migrate.py` (přísné `verify_redacted`, stejné regiony, např. SYN-A01 `4958e179…`: 13 oblastí) přeskočil 0 z 91 dokumentů, kdežto `measure.py` u týchž dokumentů zaznamenal 1 přísné hlášení. Příčinu jsem nestihl dohledat (měření bylo na pokyn zastaveno); než se na 13 % spoléhá, je třeba ověřit na jednom dokumentu.

## 1. Co se měřilo a jak

**Data.** (a) 165 dokumentů z `dataset/mapping.json` (20 případů SYN-*, generické vektorové podpisy, skupina A), 489 stran. (b) 16 PDF původních případů `solom-rec` a `stavby-fiser` (rukopis, skupina B), 74 stran. Skupiny se nikdy nesčítají.

**Pravda.** Skupina A: `eval/truth.json` (z anotací balíku, `marks[].signature_bbox`), 323 podpisů na 129 dokumentech (36 dokumentů je bez podpisu). Skupina B: jen počty podpisů na straně z `eval/originals_review.yaml` (37 podpisů na 15 stranách, jeden posuzovatel bez druhé kontroly), poloha není známa.

**Redakce.** Pro každé PDF: nálezy detektoru (dle scénáře) → `conservative_regions` (nebo varianta zón) → `redact_pdf` → `verify_redacted` → `changed_outside`. Zamaskované PDF se nikam nezapisuje (jen lokálně).

**Scénáře nálezů.**

| Scénář | Nálezy | Co představuje |
|---|---|---|
| `zones` | žádné | nejhorší případ: detektor nenašel nic, zbývají jen zóny |
| `pipeline` | Textract → vložené obrázky → inkoust nad popiskem (OCR z Textractu); u digitálních PDF místo Textractu lokální zálohy (vložené obrázky, inkoust nad popiskem, vektorové tahy) | to, co dělá pipeline (`default_detector`); Textract se volal jen pro 61 skenů/fotek skupiny A a 16 PDF skupiny B (odpovědi se cachují) |

**Metrika (skupina A), po podpisu.** (i) pokrytí pravdivého boxu černou maskou a maskou nebo zónou; (ii) pixelová kontrola: strana se vykreslí bez textové vrstvy (150 dpi) před a po redakci, „inkoust“ = pixely o ≥ 40 úrovní tmavší než pozadí strany; černé výplně z redakce a jejich okraj (3 px, antialiasing) se nepočítají jako zbytek. Podpis je **nečitelný**, když v boxu zbylo ≤ 10 % původního inkoustu (nebo méně než 30 pixelů). Zbytky nad 10 % jsem navíc prohlédl očima na výřezech (první verze metriky počítala okraj výplně jako inkoust a hlásila 28 falešných zbytků; po opravě zbytky u `v2` zmizely a u `v1` zůstaly 4 skutečné: pokrytí 0 %, inkoust beze změny).

**Interval:** Wilsonův 95% interval podílu.

## 2. Skupina A (generic): úplnost podle scénáře a vstupu

Podíl pravdivých podpisů, které po redakci nejsou čitelné. Typy vstupu podle manifestu balíku (`quality`).

| Vstup | podpisů | `zones` `v1` (jen zóny) | `zones` `v2` (jen zóny) | **`pipeline` `v1`** (stávající zóny + detekce) | **`pipeline` `v2`** (nové zóny + detekce) |
|---|---|---|---|---|---|
| digital | 221 | 15 (6,8 %) | **221 (100 %; 98,3 až 100 %)** | **221 (100 %; 98,3 až 100 %)** | **221 (100 %; 98,3 až 100 %)** |
| gray_scan | 18 | 0 | 0 | 16 (88,9 %; 67,2 až 96,9 %) | 18 (100 %; 82,4 až 100 %) |
| office_scan | 13 | 0 | 0 | 13 (100 %; 77,2 až 100 %) | 13 (100 %; 77,2 až 100 %) |
| faded | 16 | 0 | 0 | 15 (93,8 %; 71,7 až 98,9 %) | 16 (100 %; 80,6 až 100 %) |
| mobile | 14 | 0 | 0 | 13 (92,9 %; 68,5 až 98,7 %) | 14 (100 %; 78,5 až 100 %) |
| fax | 10 | 0 | 0 | 10 (100 %; 72,2 až 100 %) | 10 (100 %; 72,2 až 100 %) |
| mixed | 10 | 0 | 0 | 10 (100 %; 72,2 až 100 %) | 10 (100 %; 72,2 až 100 %) |
| compressed | 9 | 0 | 0 | 9 (100 %; 70,1 až 100 %) | 9 (100 %; 70,1 až 100 %) |
| low_dpi | 8 | 0 | 0 | 8 (100 %; 67,6 až 100 %) | 8 (100 %; 67,6 až 100 %) |
| photocopy | 4 | 0 | 0 | 4 (100 %; 51,0 až 100 %) | 4 (100 %; 51,0 až 100 %) |
| **všechny** | **323** | **15 (4,6 %; 2,8 až 7,5 %)** | **221 (68,4 %; 63,2 až 73,2 %)** | **319 (98,8 %; 96,9 až 99,5 %)** | **323 (100 %; 98,8 až 100 %)** |

Počty u typů mimo `digital` jsou malé (4 až 18 podpisů), intervaly široké: „100 %“ u `photocopy` znamená „nejméně 51 %“ s 95% jistotou. Skeny dohromady (102 podpisů): `pipeline` `v1` 98 z 102 (96,1 %; 90,3 až 98,5 %), `pipeline` `v2` 102 ze 102 (96,4 až 100 %).

**Podpisy, které zůstaly čitelné (`pipeline` `v1`, všechny 4 prohlédnuty).** Pokrytí maskou i zónou 0 %, inkoust v boxu beze změny: Textract podpis nenašel, zóny na skenu nevznikly (žádná textová vrstva).

| Dokument | Strana | Role | Typ |
|---|---|---|---|
| SYN-C04 / `cfdbb789-1f9b-5492-ace1-fcc75a0641a9` | 3 | borrower | faded |
| SYN-C04 / `01fcd768-855f-5ac7-af3e-604d6a7d0348` | 1 | provider | gray_scan |
| SYN-C08 / `cf5c4adb-7e26-5361-aeaa-64f02e0c7a19` | 2 | borrower | gray_scan |
| SYN-C06 / `7f7355af-332d-5633-95ac-939a4f9871c3` | 2 | borrower | mobile |

U `pipeline` `v2` zbylo 0 podpisů s inkoustem nad 10 %. Černé překrytí (≥ 90 % boxu maskou nálezu) mají jen 312 z 323; zbytek chrání zóna (obrázky a kresby v zóně jsou pryč).

## 3. Skupina B (rukopis): ruční prohlídka

Vykreslil jsem originál a zamaskovanou kopii všech **15 stran se 37 podpisy** (90 dpi, vedle sebe) a spočítal podpisy, které zůstaly čitelné. Stran s podpisem je v původních PDF jen 15 z 74 (zadání počítalo s 40; zbylých 59 stran podpis podle ruční kontroly nemá a neprohlížel jsem je). Zvětšeně jsem prohlédl jedinou nejasnou stranu (`10_Podklady k výlatě_objednávka`, strana 1).

| Skupina B, 37 podpisů | čitelné po redakci | nečitelné | zbytky |
|---|---|---|---|
| **`pipeline` `v1`** (stávající zóny + detekce) | **2** | 35 z 37 (94,6 %; 82,3 až 98,5 %) | ocas tahu u 1 podpisu (nečitelný), slabý oblouk nad černým polem u razítka (`stavby-fiser/10_Podklady k výplatě _Objednávka + TS`, strana 9) |
| **`pipeline` `v2`** (nové zóny + detekce) | **0** | 37 z 37 (90,6 až 100 %) | ocas tahu u 1 podpisu (modrý oblouk vpravo od černého rámečku, jen zakřivení; `solom-rec/10_Podklady k výlatě_objednávka` strana 1, „Vystavil: Ing. Jarmila Kotrbatá“) |

Čitelné podpisy při `v1`: `solom-rec/11_Podklady k výplatě _ Protokol.pdf`, strana 3 (rukopisný podpis vlevo u „Datum a podpis“) a strana 4 (podpis technika vlevo dole „Podpis technika“). Oba jsou ve skenu, Textract je nenašel a skenu chybí textová vrstva pro zóny. Zóny `v2` (z OCR řádků Textractu) je zachytily.

Pro skupinu B platí zásadní omezení: **malý vzorek, jeden posuzovatel (já, bez druhé kontroly), zóny `v2` jsem ladil i podle těchto stran** (rozhodnutí o OCR zónách). Skutečné míry úplnosti u cizích rukopisných skenů tak z toho odvodit nejde. Na těchto 15 stranách `v1` zbytek nechala, `v2` ne.

## 4. Kolaterální změna

| Skupina | PDF | strany | změna mimo oblasti (podíl pixelů strany): průměr / 95. perc. / max | plocha oblastí (podíl strany): průměr / 95. perc. / max | velikost souboru × (medián / max) | `verify_redacted` s problémem |
|---|---|---|---|---|---|---|
| **`v1`**, generic digital | 104 | 397 | 0,2 % / 0,4 % / 0,5 % | 3,7 % / 24,1 % / 25,8 % | 0,93 / 0,98 | 0 |
| **`v1`**, generic skeny a fotky | 61 | 92 | 0,0 % / 0,0 % / 0,0 % | 2,2 % / 5,8 % / 6,5 % | 2,97 / 4,79 | 0 |
| **`v1`**, original (rukopis) | 16 | 74 | 0,0 % / 0,0 % / 0,3 % | 3,7 % / 26,6 % / 37,4 % | 1,04 / 2,88 | 0 |
| **`v2`**, generic digital | 104 | 397 | 0,2 % / 0,5 % / 4,5 % | 17,8 % / 37,7 % / 39,7 % | 0,93 / 0,98 | 0 |
| **`v2`**, generic skeny a fotky | 61 | 92 | 0,0 % / 0,0 % / 0,5 % | 24,5 % / 39,1 % / 39,8 % | 2,40 / 4,63 | 0 |
| **`v2`**, original (rukopis) | 16 | 74 | 0,0 % / 0,4 % / 0,6 % | 15,3 % / 46,2 % / 54,9 % | 1,02 / 2,15 | **1** |

Plocha oblastí = zóny a černé výplně dohromady (podíl strany, průměr přes všechny strany včetně těch bez podpisu). U digitálního PDF zóna odstraní jen kresby a vložené obrázky, které ji dotýkají (rámečky tabulek, čáry), takže se vykreslení mimo oblasti změní o ≤ 0,5 % pixelů; text zůstává (verifikováno: `changed_outside`). **U skenů zóna přepíše pixely obrazu včetně tištěného textu**: `v2` tak na skenu odstraní průměrně čtvrtinu plochy strany (až 40 %), na vykreslených stranách skupiny B je vidět bílé nebo černé pole přes spodní část strany včetně popisků u podpisů (např. „Jméno zástupce servisu“). Velikost skenů roste 2,4× až 4,8× (přepsané obrázky).

`verify_redacted` s problémem u `v2`: `solom-rec/11_Podklady k výplatě _ Protokol.pdf`, strana 3: „v oblasti label zůstal obrázek nebo kresba“. V zóně zůstalo 0,2 % tmavých pixelů (okraj zóny na natočeném skenu); dokument tedy není „čistý“ a přísná migrace ho přeskočí.

## 5. Nález ve `verify_redacted`

Přísné `verify_redacted` selhalo u **24 ze 181 dokumentů (13,3 %) při `pipeline` `v1`** (dokumenty skupiny A i B; u `v2` 25, u `v3` 26, u `v4` 25) a **vždy jen** hlášením „text v oblasti full“. Příčina: `get_text("words", clip=oblast)` vrací slova, která oblast jen škrtnou. Příklad (SYN-A01 `4958e179…`, strana 6): tištěné jméno „Matěj Vřesník“ začíná 0,34 b. nad dolním okrajem oblasti full; redakce text, který leží téměř celý mimo oblast, ponechá, ověření ho vidí jako zbytek („ěj“, „Vř“, „ík“). Nejde o podpis ani o čitelný obsah oblasti. Důsledek: v pipeline by takový dokument skončil `REDACTION_VERIFY_FAILED` a nic by se nezapsalo.

Oprava (nepřevzatá do knihovny, jen v `measure/`): `verify_tolerant.py` ponechá chybu, jen když slovo leží v oblasti z ≥ 30 % plochy. Doporučení vlastníkovi `privacy/`: stejnou podmínku dát do `verify_redacted`. V tabulkách výše (`verify_redacted` s problémem) je počet **po** obálce; počet před ní je v `verify_raw_n` ve výsledcích.

## 6. Doporučení k zónám

1. **Zakládat zóny i podle role a funkce, nejen podle „podpis“** (`measure/zones.py`, `v2`): zóna 45 mm **nad** řádkem s funkcí („jednatel“, „zmocněnec“, „prokurista“, …; jméno leží mezi funkcí a podpisem), 55 mm **pod** řádkem s hlavičkou role („Poskytovatel“, „Příjemce“, „Ručitel“, „Dodavatel“, …) a 45 mm nad popiskem „podpis“; šířka 80 mm od levé hrany řádku (sloupce podpisů jsou ~91 mm od sebe). Na digitálních PDF stojí zóna jen kresby, které dotýká (≤ 0,5 % pixelů mimo oblasti), text zůstává. Samotné zóny `v2` skryly 221 ze 221 digitálních podpisů i bez detektoru.
2. **Zóny na skenech vznikají jen z OCR řádků** (`ocr.lines`, u pipeline Textract). Bez OCR nevzniknou žádné (zóny `v1` na skenu: nikdy). `v2` zachránila všech 4 podpisy, které `v1` na skenech nechala. Cena: ztráta tištěného textu v zóně (průměrně čtvrtina plochy strany). Doporučení: **OCR a text/popisky vzít před redakcí** (pipeline je počítá z originálu v paměti: role, popisek, text jdou do `signatures.json` a `text.txt` předtím), a zamaskovaný sken brát jako podklad jen pro lidskou kontrolu a vektory stránek. Užší zóny pro skeny (`v3`: 30 mm nad funkcí, 40 mm pod rolí, 35 mm nad popiskem) plochu zmenšily jen z 24,5 % na 20,0 % a přidaly 2 dokumenty s hlášením ověření; nestojí za to.
3. **Sjednocený blok (`block`)** na vlastní plochu nemá velký vliv: `v4` (= `v2` bez bloku) měla plochu 17,2 % / 23,8 % (digital / sken) proti 17,8 % / 24,5 %; pokrytí stejné (323 ze 323).
4. **Neslibovat 100 %.** Po `v2` je úplnost na datech, na kterých se zóny ladily, 100 %; to není odhad pro cizí dokumenty (jiné rozložení bloku, podpis daleko od jména a hlavičky, podpis pod popiskem, jiný jazyk). Tvrzení zůstává „odstraněno, kde jsme podpis našli nebo čekali“ a doporučení z [be-validator-agent/docs/validator-agent-privacy.md](../../../../be-validator-agent/docs/validator-agent-privacy.md) část 4.3 platí: omezit čtení bucketu a politiku KMS klíče jako druhou vrstvu.
5. **Převzít `verify_tolerant`** do `verify_redacted` (část 5) a **přidat do `conservative_regions` zóny podle funkce a role** (a OCR řádky u stran bez textové vrstvy). Do knihovny jsem je nepřidal (mimo moje oblast); `measure/zones.py` je na to připravené.

## 7. Co měření nepokrývá

- Zóny `v2` jsou navržené na týchž datech: skupina A není nezávislý test zón (rozložení bloku generátoru je ve všech dokumentech stejné); skupina B je malá a ladil jsem i podle ní.
- Pravdivý box je z anotace v bodech PDF; u skenů s posunem nebo natočením může být mimo. Pixelová kontrola počítá inkoust v boxu, ne přesnou polohu; zbytky jsem prohlížel očima, ale nepodařilo se ověřit, že u `v2` nezbyl nečitelný zlomek podpisu mimo box.
- Pixelová kontrola bere inkoust jako „tmavší o 40 úrovní než pozadí“; velmi světlý podpis (vybledlé skeny, fax) může být pod prahem. Typ `faded` měl inkoust ve všech 16 podpisech (pozadí 240+), ale na horších datech to platit nemusí.
- Strany bez podpisu v anotaci se neprohlížely; podpisy mimo anotaci nejsou známy.
- Textract se volal jen pro skeny a rukopis (digitální PDF dostala lokální zálohy bez Textractu); úplnost pipeline u digitálních PDF s Textractem (94 % podle `eval/README.md`) tu není měřená. U digitálních je pokrytí zajištěno zónami `v2` (221 ze 221 i bez detektoru).
- Čitelnost zbytků hodnotí člověk (já); nebyla druhá kontrola.

## 8. Migrace (krok 4): stav

**Na pokyn uživatele se migrace zastavila po jednom testovacím dokumentu.** Ostatní dokumenty se nezapsaly. Skript `migrate.py` je hotový a v režimu `--dry-run` byl spuštěn na 91 dokumentech z asi 204 (dry-run se po pokynu přerušil).

**Dry-run (91 dokumentů, případy 17794315-26, SYN-A01 až SYN-C04):** 0 přeskočených při přísném `verify_redacted`, 0 chyb; u 9 dokumentů `redacted/…pdf` už existuje se stejným `original-sha256` (zapsala ho pipeline, nepřepsalo by se); u 31 dokumentů existují vektory `#p<n>` k přepočtu (u 60 žádné); `signatures.json` k aktualizaci u 18 dokumentů; u 51 dokumentů v tabulce `wonderfulkb-uw-document-analysis` řádek není (atribut se nezapíše), u 8 už `original_sha256` je. Dokumenty skupiny B (původní případy) v dry-runu dokončeny nebyly. (Výpočet `--all` trvá na vytíženém stroji asi hodinu; nespuštěno znovu.)

**Skutečný zápis (jeden dokument):** `SYN-A01 / 34fcd896-107a-583f-a406-6a8100cf8150`, `--apply --only`. Nezávisle ověřeno po zápisu (round-trip každého výřezu přes KMS i s odmítnutím špatného `signature_id`, hash a velikost originálu v metadatech, rozdíl verzí `signatures.json`, vektor, řádek tabulky). **Přesný seznam zapsaných věcí a rozdíl proti původnímu stavu:**

| Co | Klíč / místo | Rozdíl proti původnímu stavu |
|---|---|---|
| zamaskovaná kopie (NOVÝ objekt) | `cases/SYN-A01/redacted/34fcd896-107a-583f-a406-6a8100cf8150.pdf` (VersionId `jieY.j6FE3fQ9vb0mNF.uuQFSTvBxNIO`, 51 513 B) | dříve neexistoval; metadata `original-sha256=35659ad0…3f4c`, `original-size=58085`, `project=wonderfulkb` |
| zašifrované výřezy (5 NOVÝCH objektů) | `cases/SYN-A01/analysis/34fcd896-…/signatures/sig_01.png.enc` až `sig_05.png.enc` | nové; formát `WKBS` (AES-256-GCM, KMS `alias/wonderfulkb-signatures`, kontext case/document/signature) |
| zkreslené náhledy (5 NOVÝCH objektů) | `…/signatures/sig_01.preview.png` až `sig_05.preview.png` | nové |
| `signatures.json` (NOVÁ VERZE) | `cases/SYN-A01/analysis/34fcd896-…/signatures.json`, nová verze `Ac8pgHKJSQ4Ne031vDR9udMgK3hxVUuN`, 2 836 B; předchozí verze `_ykx6brllk6pdp.Lfr2kcCH1.eI4OmLS`, 1 641 B zůstává | u každého z 5 podpisů přibyla pole `crop_s3_key` (`….png.enc`), `crop_encrypted: true`, `preview_s3_key`; ostatní pole a hlavička beze změny (porovnáno) |
| vektory (4 PŘEPSANÉ) | index `wonderfulkb-image`, klíče `34fcd896-…#p1` až `#p4` | stejný klíč a stejná metadata, vektor přepočten z hlediska stránek vykreslených ze zamaskovaného PDF (110 dpi); **původní hodnoty vektorů se nedají vrátit** (S3 Vectors nemá verze; obnova = přepočet z originálu) |
| řádek tabulky | `wonderfulkb-uw-document-analysis`, `case_id=SYN-A01`, `document_id=34fcd896-…` | přibyl atribut `original_sha256` (hodnota = SHA-256 originálu); ostatní atributy beze změny |

Beze změny zůstalo: čitelný originál `…/original/34fcd896-….pdf`, čitelné výřezy `sig_01.png` až `sig_05.png` a stránky `pages/<n>.png`. Nic se nemazalo. Žádné jiné zápisy do S3, vektorů ani tabulek se neprovedly.

**Výchozí nastavení pro později:** zóny `--zones v2`, detekce `--detect pipeline` (Textract jen pro skeny, `--textract all` pro všechna PDF), přísné ověření (`--tolerant` jen po rozhodnutí), `--rpm 20`; při souběžných shardech (`--shard K/N`) rozdělit `--rpm` (limit Bedrocku je sdílený, 50/min na tým). Otevřené: dokument `solom-rec/11_Podklady k výplatě _ Protokol` neprojde ověřením při `v2` (část 4); doporučuji migrovat až po vyřešení rozporu výše a po schválení uživatele.
