# Měření detekce podpisů: Textract samotný vs. záloha (19. 10. 2026)

Skripty: `eval_detectors.py` (skupina A proti anotacím, `python eval/eval_detectors.py PACK_ROOT --cache DIR --found-cache DIR`).
Skupiny se **nesčítají** a výsledek jedné se nepřenáší na druhou.

Textract běžel jako v modulu: každá strana vykreslená na PNG (150 dpi), `AnalyzeDocument(SIGNATURES)`,
489 stran balíku, odpovědi v cache. Číslo se mírně liší od reportu OCR session (297 z 323, 92,0 %): ten řezal
strany na jednostránková PDF a párování bylo jiné; moje párování je zvlášť popsané níže.

## Metodika a proč 94,1 % proti 92,0 %

| | tento modul (`eval_detectors.py`) | report OCR session (`signatures-eval/`) |
|---|---|---|
| Vstup do Textractu | každá strana vykreslená PyMuPDF na **PNG 150 dpi**, synchronní `AnalyzeDocument(SIGNATURES)`, jedna strana = jedno volání | každá strana vyříznutá do **jednostránkového PDF** (bajty), synchronní `AnalyzeDocument(SIGNATURES)`; produkční asynchronní cesta (`StartDocumentAnalysis` ze S3) běžela jen u skupiny B |
| Párování | 1:1, každá pravda si vezme volný nález s nejvyšším IoU; volná shoda IoU ≥ 0,2 nebo střed v pravdě +10 % | 1:1, stejné pravidlo shody; jak vybírá mezi více kandidáty, jsem nezjišťoval |
| Výsledek (skupina A) | 304 z 323 (94,1 %), 1 falešný, všechny podpisy 111/129 | 297 z 323 (92,0 %), 1 falešný, všechny podpisy 107/129 |

Textract je v obou případech týž (`SIGNATURES`); rozdíl 7 nálezů z 323 (2,2 procentního bodu) pochází z jiného vstupu
a/nebo jiného výběru při párování. **Nerozlišil jsem, který z těch dvou důvodů, protože jsem oba způsoby nepustil na
stejném vstupu.** Pro absolutní číslo to znamená „asi 92 až 94 %“, pro porovnání detektorů mezi sebou platí vždy
čísla jedné metodiky, tedy v této tabulce všechna z mé (strana po straně, 150 dpi).

## Párování

Nález se s pravdou páruje 1:1 (každá pravda si vezme volný nález s nejvyšším IoU):
- **volné** (hlavní čísla): IoU ≥ 0,2, nebo střed nálezu leží uvnitř pravdivého boxu zvětšeného o 10 % (pravidlo
  OCR session, čísla jdou porovnat);
- **přísné**: IoU ≥ 0,5. Boxy vektorové zálohy zahrnují i razítko, anotace `signature_bbox` ho nemá, proto
  přísná shoda zálohy samotné vychází nízko. Sloužila jen jako kontrola.

Falešný nález = nález bez páru. Do tohoto počtu patří i druhá část téže značky (razítko odděleně od podpisu).

## Skupina A: 20 generických případů (anotace `marks[].signature_bbox`, 165 PDF, 323 podpisů)

| Podskupina | podpisů | Textract: nalezeno / úplnost / falešné | Textract + vektorová záloha: nalezeno / úplnost / falešné | dokumentů se všemi |
|---|---:|---|---|---|
| A/B vektorová PDF (10 případů) | 185 | 172 / 93,0 % / 0 | 185 / 100 % / 25 | 53 → 65 z 65 |
| C `digital` (vektorová) | 36 | 35 / 97,2 % / 1 | 36 / 100 % / 5 | 17 → 18 z 18 |
| C skeny a degradace (compressed, faded, fax, gray_scan, low_dpi, mixed, mobile, office_scan, photocopy) | 102 | 97 / 95,1 % / 0 | 97 / 95,1 % / 0 | beze změny |
| **Celkem** | 323 | **304 / 94,1 % / 1** | **318 / 98,5 % / 30** | 111 → 124 ze 129 |

- Zálohy `page_images` a `label_anchored` ve skupině A **nenašly nic**: podpisy jsou vektorové křivky, ne
  vložené obrázky, a dokumenty nemají popisek „Podpis“ (podpis stojí nad čarou a jménem). Použitelná je jen
  `vector_strokes`.
- Přírůstek je celý ve vektorových PDF. U skenů (rastr) žádná z mých záloh nemá co najít, tam zůstává
  Textract: 97 ze 102.
- Falešné nálezy zálohy v A/B vektorových PDF (25): 20 je samostatná část razítka téhož podpisu a 5 je technický
  výkres stroje v `11_Predavaci_protokol.pdf` (stejný v každém případu). Ve `digital` je 5 falešných, jejich původ
  jsem nerozebíral. Jediný falešný nález Textractu je ve `digital` (`SYN-C05/11_specifikace`, strana 1).

## Skupina B: 2 původní případy s lidskými rukopisnými podpisy (`solom-rec`, `stavby-fiser`)

Pravda je **ruční počet po dokumentech** z reportu OCR session (37 podpisů, prohlédnuto 40 stran), box pravdy
neexistuje, proto se porovnávají počty nálezů, ne polohy. Nálezy navíc oproti Textractu jsem prohlédl na výřezech.

| Konfigurace | nalezeno z 37 | úplnost | falešné nálezy |
|---|---:|---:|---|
| Textract (moje měření, strana po straně) | 25 | 68 % | neověřoval jsem znovu (OCR session žádný neviděla) |
| Textract v produkční cestě (OCR session) | 22 | 59 % | 0 |
| + `page_images` | 29 | 78 % | 0 |
| + `page_images` + `label_anchored` | 33 | 89 % | 0 |
| + `vector_strokes` | 33 | 89 % | 0 (nic nepřidal) |

Všech 8 nálezů navíc je skutečná značka: 6 podpisů a 2 razítka s podpisem na skenech. Zbývající 4 neodhalené:
dva podpisy v jednom boxu (`09_Dohoda`, `stavby-fiser/0_F_Smlouva`), modrý podpis „Vystavil“
(`solom-rec/10_objednávka`), podpisy technika a střediska (`solom-rec/11_Protokol`).

**Neodmyslitelná výhrada:** `page_images` a `label_anchored` (velikosti oblastí, filtry log) jsem navrhl a ladil
na těchto 13 PDF. Výsledek skupiny B je tedy **na ladicích datech**, nikoli nezávislé měření; na jiných rukopisných
dokumentech může být horší.

## Záloha vision LLM

Neměřeno (šetření sdíleného limitu Bedrocku). Zálohy bez modelu pokrývají vektorové a obrazové podpisy a ukotvení
na popisek, vision LLM by zbývalo na skeny bez popisku, kde je Textract jediná vrstva.

## Co z toho plyne

- Textract samotný: 94 % ve skupině A, ale 59 až 68 % na rukopisu. „Žádný podpis nenalezen“ nelze brát jako
  důkaz absence.
- Záloha zvedá skupinu B z 68 % na 89 % bez falešných nálezů (v ladicím vzorku) a vektorovou část skupiny A na
  100 %. Skeny bez popisku zůstávají na Textractu.
- Nálezy `label_anchored` a `vector_strokes` mají v poli `detector` hodnotu, která zatím **není v enumu OpenAPI**
  (jen `textract`, `vision_llm`, `page_images`).
