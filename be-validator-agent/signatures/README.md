# Signature pipeline

Podklad pro volání 3 validačního agenta (`GET /cases/{case_id}/documents/{document_id}/signatures`,
[openapi-validator-agent.yaml](../../../be-document-processing/contracts/openapi-validator-agent.yaml), plán A5 a A7 v
[validator-agent-plan.md](../docs/validator-agent-plan.md)). Výstup je přítomnost, přiřazená role a
podezření na kopii. **Pravost se neposuzuje.**

```
PDF ─▶ 1 detekce ─▶ 2 role ─▶ 3 výřez ─▶ 4 percepční hash ─▶ 5 podezření na kopii (napříč dokumenty case)
```

| Krok | Modul | Jak |
|---|---|---|
| 1 Detekce | `detect.py` | Textract `AnalyzeDocument`, `FeatureTypes=["SIGNATURES"]`, po stránkách na vykresleném PNG (150 dpi), takže bbox je relativní k vykreslené stránce. Odpovědi se cachují podle SHA-256 PNG (opakovaný běh nic nestojí). Překrývající se boxy (IoU ≥ 0,5) se slučují. |
| 2 Role | `roles.py` | Z textové vrstvy PDF (PyMuPDF), dokud nejsou k dispozici bloky z OCR (B4). Krátké řádky (≤ 8 slov) s klíčovým slovem: `provider`, `borrower`, `guarantor`, `supplier`, `buyer`, `insurer`, jinak `unknown`. Dvě pravidla, vyhrává bližší: **hlavička sloupce** (nad podpisem, vlastní sloupec ohraničuje další popisek na řádku nebo svislá čára tabulky z kresby stránky) a **přilehlý popisek** (vedle, pod, přímo nad). Názvy firem (SGEF) jsou slabší důkaz než role („Poskytovatel“), mají penalizaci. `role_evidence` je doslovný řádek. |
| 3 Výřez | `imaging.py` | Vyříznutí z PDF při 200 dpi, uložení do `LocalCropStore` (`crops/<case>/<doc>/<sig>.png`). `crop_url` zůstává `null`, předpodepsané URL zatím nevzniká. |
| 4 Hash | `imaging.py` | pHash (DCT 32×32, 64 bitů, hex 16 znaků) z **výřezu bez textu a bez tabulkových čar**: tištěné tečky, „Podpis“ a jména z masky odstraní redakce textu v okolí podpisu, dlouhé řádky a sloupce inkoustu se zahodí. Hash se počítá z ink-tight oříznutí, takže posun a okraje ho nemění. Prázdný výřez má `phash: null`. |
| 5 Kopie | `copycheck.py` | Kandidáti podle Hammingovy vzdálenosti ≤ 8 z 64 bitů, potvrzení Diceovým koeficientem inkoustových masek ≥ 0,90 a podobným poměrem stran. Jen **jiné dokumenty téhož case**. `level`: `none` / `suspected`, `matches[]` se skóre. |

## Spuštění

```bash
python -m venv venv && venv/bin/pip install -r requirements.txt pytest
venv/bin/python -m pytest tests                     # syntetická PDF, Textract se nevolá
export AWS_PROFILE=hackathon AWS_REGION=eu-central-1
venv/bin/python -m signature_pipeline CASE_ID a.pdf b.pdf --out out.json --crops crops --cache .textract-cache
```

Z Pythonu: `process_case(case_id, {document_id: cesta_nebo_bytes}, TextractDetector(cache_dir=...), LocalCropStore("crops"))`
vrací `{document_id: {"case_id", "document_id", "signatures": [...]}}` ve tvaru volání 3 (bez `similar_signatures`
a `vector`, ty vyžadují S3 Vectors a model podpisu, který zatím není zvolený).

## Záložní detekce (`PageImageDetector`, `CombinedDetector`)

Textract přehlíží rukopisné podpisy, proto je k dispozici záloha bez služby a bez nákladů: vložené obrázky na
born-digital stránce, které mají velikost podpisu a tenké tahy na světlém pozadí. Loga (horní okraj,
opakují se na stránkách), čárové kódy (hustý inkoust) a stránky s mnoha malými obrázky (text uložený jako
obrázky, např. skenovaná tabulka) se vyřadí. Box se kolem obrázku zvětší, protože bývá příliš těsný. Do
výsledku jdou jen nálezy, které nepokrývá žádný box Textractu (`detector: "page_images"`, `detection_score: null`).
V CLI jsou zálohy `page_images` a `label_anchored` zapnuté vždy, `--only-textract` je vypne, `--vector` přidá `vector_strokes`.

Další dvě zálohy: `LabelAnchoredDetector` (oblast nad popiskem „Podpis“ bez tištěného textu, rozhodne zbylý inkoust;
u skenů se tištěný text maluje bíle podle řádků Textractu) a `VectorStrokeDetector` (shluky křivek velikosti podpisu
pro vektorově kreslené podpisy). `CombinedDetector(textract, images, label, vector)` bere detektory v pořadí důvěry a
přidává jen boxy, které žádný dřívější detektor neoznačil.

**Měření** (podrobně `eval/README.md`, po skupinách): ve skupině A (20 generických případů, anotace) Textract 94,1 %,
s vektorovou zálohou 98,5 % (falešné nálezy 1 → 30, z toho 20 jsou části razítek); skeny zůstávají na Textractu (95,1 %).
Ve skupině B (rukopis, ruční počet) Textract 68 %, se zálohami 89 %, 8 nálezů navíc je všech 8 skutečných značek, ale zálohy
jsem ladil na týchž 13 PDF. Zálohu přes vision LLM jsem neměřil. Hodnoty `label_anchored` a `vector_strokes` v poli `detector`
zatím nejsou v enumu OpenAPI.

## Napojení na ostatní části

- **Rozhraní** z [validator-agent-storage.md](../../../be-validator-agent/docs/validator-agent-storage.md): `detect_signatures(pdf_path, ocr_text_blocks=None) -> list[dict]` (`interface.py`), bez `crop_url`. Podezření na kopii potřebuje ostatní dokumenty case, proto ho dává jen `process_case`.
- **Detekce z `be-document-processing`** (`TextractSignatureDetector`, větev `feat-textract-signatures`): jeho nálezy se předají jako `PrecomputedDetector(items)` a Textract se nevolá podruhé. Role z PDF má přednost, role z jeho řádků Textractu je záloha pro skeny bez textové vrstvy.
- **OCR bloky**: `ocr_text_blocks` se použijí k roli jen u bloků s relativním `bbox` (výstup OCR má zatím `bbox: null`, takže se přeskočí).
- **Zápis do S3** (`store.py`) podle storage kontraktu. **Čitelné výřezy se už nezapisují** (rozhodnutí 19. 10. 2026, [validator-agent-privacy.md](../../../be-validator-agent/docs/validator-agent-privacy.md)): `S3CropStore` bez přepínače při `save` selže (`PlaintextNotAllowed`), čitelný `.png` jen s `allow_plain=True` (vývoj). `write_signatures_json` nikdy nepřepíše existující `signatures.json` (`FileExistsError`, výjimka jen s `overwrite=True`).
- **Soukromí (přepínač `encrypt=True`, výchozí vypnuto)**: výřez se řeže z originálu v paměti, spočítá se `phash` a před šifrováním se zavolá volitelný hák `on_plain(case_id, document_id, signature_id, png)` (sem patří embedding výřezu, `embed.write_signature_vectors`, takže se výřez nikdy nečte zpět z S3); pak `signature_privacy.encrypt_image` (AES-256-GCM, KMS `alias/wonderfulkb-signatures`, kontext case/document/signature) → `signatures/<sig>.png.enc` a zkreslený `signatures/<sig>.preview.png`; čitelné PNG vznikne jen v paměti. Do `signatures.json` jde `crop_s3_key` (klíč `.png.enc`) a `crop_encrypted: true`, `crop_url` se nevrací. Knihovna `signature_privacy` je v `infra/validator-agent/privacy/` (načte se odtud, potřebuje `cryptography`). Ověřeno testem s lokálním klíčem; **proti skutečnému KMS ani bucketu se nespouštělo a migrace dřívějších čitelných výřezů se neprovedla.**
- **Výchozí detektory**: Textract → `page_images` → `label_anchored` (`default_detector`), `vector_strokes` jen volitelně (`--vector`, `default_detector(..., vector=True)`), protože přidává falešné nálezy (části razítek). V `detector` je u každého nálezu zdroj, který ho našel. CLI: `--only-textract`, `--vector`.
- **PyMuPDF (výjimka ze storage kontraktu)**: kontrakt PyMuPDF pro ostatní moduly zakazuje, protože se na Pythonu 3.14 kompiluje a visí. Tento modul ho potřebuje (role používají svislé čáry tabulky z kresby stránky, text pod podpisem se pro hash maže redakcí), proto má výjimku. Instalace jen z hotového kola: `pip install --only-binary :all: -r requirements.txt` (kolo existuje, ověřeno 1.28.2).

## Co je a není hotové

- Kód je v `signature_pipeline/`, testy v `tests/` (30, syntetická PDF s kresleným „podpisem“).
- Detektor je výměnný (`detect(doc) -> [Detection]`); záloha vision LLM zatím není napsaná.
- Skeny bez textové vrstvy dostanou `role: "unknown"`, role z nich musí přijít z OCR bloků (B4).
- Textract občas dvojici podpisů vedle sebe sloučí do jednoho boxu a občas podpis vynechá (na 14 vzorových PDF
  např. chybí levý podpis v `4_Form_Ručení`, v `0_F_Smlouva` jsou dva podpisy v jednom boxu); skóre se nepoužívá
  jako práh.
- Vzorový výstup nad vzorovými PDF (po případech `solom` a `stavby`): `examples/sample-output.json`.
- Zápis do S3 Vectors (`wonderfulkb-signatures`) modul nedělá (model podpisu není zvolený).
- **Co už v bucketu leží čitelně:** 19. 10. 2026 jsem na čtyřech vzorových případech zapsal 28 `signatures.json` a 42 čitelných výřezů `signatures/*.png` (před rozhodnutím o soukromí). Zůstávají tam beze změny, jejich migrace na `.png.enc` čeká na schválení uživatele; nic dalšího čitelného se nezapisuje.
