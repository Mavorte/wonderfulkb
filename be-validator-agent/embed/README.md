# embed: embeddingy a S3 Vectors

Část validačního agenta podle [be-validator-agent/docs/validator-agent-storage.md](../../../be-validator-agent/docs/validator-agent-storage.md). Počítá vektory (Bedrock Titan, 1024 dimenzí) a zapisuje/čte je v bucketu `wonderfulkb-vectors` (indexy `wonderfulkb-text`, `wonderfulkb-image`, `wonderfulkb-signatures`). Nic se nenasazuje, modul je knihovna.

## Co přibylo

| Soubor | Obsah |
|---|---|
| `embeddings.py` | `embed_text(text)`, `embed_texts([…])`, `embed_image(png_bytes)`, výběr modelu z prostředí; úprava PNG do hranic Titanu |
| `chunking.py` | `chunk_text(text)`: části 500 až 800 tokenů, hranice po odstavcích a větách, `page_from`/`page_to` (strany odděleny `\f`), `chunk_id` |
| `vectors.py` | `write_document_vectors(case_id, document_id, text, page_pngs, label=None)`, `nearest_verified(vector, index, top_k, case_id=None)`, pomocné `write_signature_vectors`, `set_verified`, `put_vectors`, `delete_vectors` |
| `clients.py` | klienti, retry s backoffem, omezovač volání Bedrocku |
| `live_check.py` | živé ověření (zapíše testovací vektory, dotáže se, smaže je) |
| `benchmark.py` | srovnání modelů leave-one-out na vzorových dokumentech (viz níže) |
| `tests/` | 31 testů s mockem Bedrocku i S3 Vectors |

Použití (z `infra/validator-agent/`):

```python
from embed import embed_text, embed_image, write_document_vectors, nearest_verified

write_document_vectors(case_id, document_id, text, page_pngs, label="smlouva_o_uveru")
vec = embed_text("Vinkulace pojistného plnění")
nearest_verified(vec, "text", top_k=5, case_id=None, exclude_document_id=None)
# -> [{key, document_id, case_id, label, score, distance, metadata}], score = 1 - cosine distance
```

`page_pngs` je seznam PNG (první = strana 1) nebo `{číslo strany: PNG}`. `index` je `text` / `image` / `signatures` nebo plný název. Přihlášení: výchozí řetěz boto3; `WONDERFULKB_AWS_PROFILE=hackathon` vybere profil.

## Spuštění

```bash
python3 -m venv .venv && .venv/bin/pip install -r embed/requirements.txt   # v infra/validator-agent/
.venv/bin/python -m pytest embed/tests -q                                    # mock, bez AWS
WONDERFULKB_AWS_PROFILE=hackathon .venv/bin/python -m embed.live_check      # živě, ~15 volání Bedrocku
```

## Co jsem ověřil živě (19. 10. 2026, `eu-central-1`, účet <ACCOUNT_ID>)

**Bedrock, oba modely běží, oba vrací 1024 dimenzí:**

| Model | Parametr | Výsledek | Latence jednoho volání |
|---|---|---|---|
| `amazon.titan-embed-text-v2:0` | `dimensions=1024`, `normalize=true` | 1024 floatů | 0,2 s |
| `amazon.titan-embed-image-v1` | `outputEmbeddingLength=1024` | 1024 floatů | 1,2 s |

Alternativa tedy není potřeba a indexy se neměnily. Titan Multimodal bere PNG se stranami 128 až 2048 px a do 5 MB; `prepare_png` zmenší na delší stranu 1024 px, zvětší malé výřezy na min. 128 px a odstraní průhlednost.

**Tokeny:** `inputTextTokenCount` vyšel na vzorku z Ručení 2,05 znaku na token (569 znaků = 278 tokenů). Chunk 500 až 800 tokenů je proto v kódu ~1000 až 1600 znaků (`CHARS_PER_TOKEN = 2.0`). Limit Titanu je 8192 tokenů, jsme daleko pod.

**End-to-end** (`live_check.py`; 3 textové dokumenty ze `docs/vzorove-dokumenty/text/`, 2 PDF stažená ze S3 `cases/{solom-rec,stavby-fiser}/original/` a vykreslená přes pypdfium2, dohromady 9 textových a 4 obrazové vektory):

- Před ověřením vrací `nearest_verified` prázdný seznam; po `set_verified` vrací jen ověřené vektory.
- Dotaz vektorem části dokumentu A: na prvním místě ta samá část (score 1,0), pak vinkulace z druhého případu (0,59; nejbližší vektor jiného dokumentu), dokument C (neověřený) se nevrátil nikdy.
- Filtr `case_id` vrátí jen vektory daného případu; `exclude_document_id` vynechá vlastní dokument.
- Obraz: stránka 1 vinkulace Solom Rec je nejblíž stránce 1 vinkulace Stavby Fišer (0,966) a straně 2 (0,55).
- Zpoždění zápis → dotaz: vektor je viditelný v dotazu s filtrem **do ~0,1 s** po `put_vectors` (měřeno dvakrát: 0,109 a 0,111 s, po `set_verified`); S3 Vectors jsou při zápisu konzistentní, žádné čekání navíc netřeba. Zápis jednoho dokumentu včetně embeddingů trval 1,5 až 2,0 s (dominuje Bedrock).
- Idempotence: opakovaný zápis stejného dokumentu dá stejné klíče a nezvýší počet vektorů.
- Úklid: smazal jsem jen klíče zapsané testem (`test-embed-<run>-*`); `list-vectors` na indexech text i image po běhu vrací 0.

## Výběr modelu (`EMBED_TEXT_MODEL`, `EMBED_IMAGE_MODEL`)

| Proměnná | Hodnoty | Výchozí |
|---|---|---|
| `EMBED_TEXT_MODEL` | `amazon.titan-embed-text-v2:0`, `cohere.embed-v4:0` | Titan Text v2 |
| `EMBED_IMAGE_MODEL` | `amazon.titan-embed-image-v1`, `cohere.embed-v4:0` | Titan Multimodal |

Cohere v4 se v eu-central-1 volá přes inference profil `eu.cohere.embed-v4:0` (holé ID `cohere.embed-v4:0` Bedrock odmítne; `global.` profil také existuje, `eu.` drží data v EU), s `output_dimension=1024`, `embedding_types=["float"]`, textem `input_type=search_document` (dotazy `search_query` přes `embed_text(q, input_type="search_query")`) a obrázkem `input_type=image`. Texty posílá po dávkách po 16 (`embed_texts`).

Index se nemění (1024 dimenzí, cosine). Pravidlo proti míchání: `model` a `model_version` (`v2` / `v1` / `v4`) jdou do metadat každého vektoru a `nearest_verified` ve výchozím stavu přidá filtr na aktuálně nastavený model indexu, takže vektory dvou modelů se nikdy nesrovnávají (`any_model=True` filtr vypne). Po přechodu na jiný model je potřeba dokumenty znovu zpracovat (`write_document_vectors`), jinak `nearest_verified` nic nenajde. Starší vektory zůstanou v indexu, dokud je nepřepíše stejný klíč.

## Benchmark modelů (19. 10. 2026)

`python -m embed.benchmark` (viz docstring). Leave-one-out: každý dokument (text: průměr vektorů prvních 3 částí) nebo stránka (obraz: prvních 2 strany každého PDF, PNG zmenšené na max. 1024 px) hledá nejbližší **jiný** dokument; úspěch = nejbližší má stejný typ (číselný prefix názvu, jen pro vyhodnocení). `cross_case` bere sousedy jen z druhé rodiny případů (Stavby Fišer ↔ Solom Rec + jeho upravená varianta `unhappy_scenario`). Korpus: 22 textů (16 výpisů ze `docs/vzorove-dokumenty/text/` + PDF z `unhappy_scenario` přes pypdf; 3 prázdné vyřazeny), 25 PDF, 48 stránek, 10 typů; hodnoceny jen typy s protějškem. **Vzorek je malý** (19 dokumentů, 47 stránek), rozdíly o jeden dokument nic neříkají.

| Model | Úloha | top-1 vše | top-1 napříč případy | MRR | rozestup | dotaz větou | latence (medián) | cena |
|---|---|---|---|---|---|---|---|---|
| Titan Text v2 (1024) | text | **0,947** (18/19) | **0,933** (14/15) | 0,950 | 0,29 | 6/8 | 122 ms | ~0,011 USD / 1000 částí (529 tokenů) |
| Titan Multimodal (1024) | obraz | **0,660** (31/47) | **0,639** (23/36) | 0,698 | −0,008 | – | 190 ms | 0,06 USD / 1000 obrázků |
| Cohere Embed v4 (1024) | text | **neměřeno** | | | | | (0,24 až 1,0 s při sondě) | 0,12 USD / 1M tokenů (agregátory) |
| Cohere Embed v4 (1024) | obraz | **neměřeno** | | | | | (0,27 s při sondě) | 0,47 USD / 1M tokenů obrazu (agregátory) |
| Cohere Multilingual v3 (1024) | text | **neměřeno** | | | | | | 0,10 USD / 1M tokenů |

Ceny Cohere jsou z veřejných agregátorů (ne z ceníku AWS), ceny Titanu z launch postu AWS a agregátorů; počítej s nimi jen řádově.

**Proč Cohere není změřen:** při první sondě v eu-central-1 běžel `eu.cohere.embed-v4:0` (text, `search_query`, obraz; 1024 dimenzí, 1536 bez `output_dimension`; latence 0,99 s první volání, pak 0,24 až 0,27 s) a `cohere.embed-multilingual-v3` také. O pár desítek minut později začal každý Cohere model vracet `AccessDeniedException` (chybí oprávnění `aws-marketplace:ViewSubscriptions` / `Subscribe`; „subscription cannot be completed at this time"), zatímco Titan běží. `get-foundation-model-availability` hlásí `AUTHORIZED` / `AVAILABLE`. Odběr přes Marketplace jsem nezakládal (změna účtu mimo můj úkol). Až půjde volat, stačí

```bash
WONDERFULKB_AWS_PROFILE=hackathon python -m embed.benchmark --models cohere-v4-text cohere-v4-image cohere-multilingual-v3 --out vysledky.json
```

(Titan výsledky se berou z diskové cache `--cache-dir`, nová volání jsou jen Cohere, asi 75 při 25 voláních/min.)

**Co z naměřeného plyne:**
- Text: Titan Text v2 je na typech dokumentů dobrý (jediná chyba je typ 10, „guláš" objednávek a technických specifikací) a levný. Cohere v4 by musel být zřetelně lepší hlavně na 1x dokumentech a dotazech větou (Titan 6/8), aby se přechod vyplatil.
- Obraz: Titan Multimodal na vzhledu stránky poznává šablonové formuláře (typy 0, 2, 3, 99 napříč případy 6/6 až 5/6), ale 1x dokumenty (10, 11), Ručení a VOP/Dohodu ne (0/6 napříč případy u 10 a 11) a rozestup vychází kolem nuly. Obrazové vektory proto nepoužívat jako hlavní signál typu dokumentu; typ určuje text. Právě obraz je místo, kde by Cohere v4 mohl přinést nejvíc, a proto stojí za změření, až bude dostupný.
- **Rozhodnutí (uživatel, 19. 10. 2026): zůstává Titan** (Text v2 a Multimodal G1, 1024 dimenzí); Cohere v4 se nepoužije, protože ho v účtu nešlo změřit (Marketplace `AccessDenied`). Výchozí hodnoty `EMBED_TEXT_MODEL` a `EMBED_IMAGE_MODEL` jsou Titan a nic se nenastavuje. Přepínač zůstává v kódu pro případ pozdějšího přechodu (jedna proměnná prostředí plus znovuzpracování dokumentů, indexy se nemění); Cohere větev je ověřená jen mockem a úvodní sondou. Další práce na benchmarku se neplánuje.

## Chování, na které se spoléhat (a které ne)

- **Klíče a metadata přesně podle kontraktu:** text `<document_id>#t<i>` (`chunk_id=c<i>`, `page_from`, `page_to`, `page=page_from`), obraz `<document_id>#p<strana>`, podpisy `<document_id>#s<n>`; vždy `case_id`, `document_id` (ne `doc_id`), `page`, `verified=false`, `model`, `model_version` (`v2` / `v1`) a `label` jen když je zadán (S3 Vectors neumí `null`). Žádný text ve filtrovatelných metadatech.
- **Idempotence:** stejný klíč přepíše vektor. Při přepisu kratším textem se navíc smažou zbylé staré části téhož dokumentu (dohledání dotazem s filtrem `document_id`, max. 100 vektorů na dokument a index).
- **Znovuzpracování resetuje `verified` na `false`**, i když byl dokument dřív ověřen. Je to záměr (nový obsah se musí potvrdit znovu); `set_verified(index, keys, verified=True, label=None)` ho vrací zpět. S3 Vectors neumí částečný update metadat, proto čte a zapisuje vektor celý.
- **Chyba v půlce nezanechá poloviční dokument:** nejdřív se spočítají všechny embeddingy, zapisuje se až potom.
- **Dávky:** `put_vectors` a `delete_vectors` po 500 vektorech, `get_vectors` po 100.
- **Retry a limit:** `ThrottlingException`, 5xx a timeouty se opakují až 6× s exponenciálním backoffem a jitterem (strop 30 s). Navíc posuvné okno omezuje proces na 30 volání Bedrocku za minutu (`WONDERFULKB_BEDROCK_RPM`, 0 = bez omezení), aby tým nenarazil na 50 za minutu. Limit je sdílený mezi všemi procesy, takže při paralelním běhu více pipeline hodnotu sniž.
- `nearest_verified` na indexu `text` vrací vektory částí, ne dokumentů: jeden dokument se může objevit víckrát. Skládání na dokumenty (nejlepší `score` na `document_id`) patří do vrstvy API. `top_k` 1 až 100.
- Podpisový index: `write_signature_vectors(case_id, document_id, [(strana, png), …])` zapisuje výřezy stejným obrazovým modelem; bez ladění, obecný embedding není model pro ověřování podpisů.

## Co ověřeno není

- Chování při souběžném zápisu více procesů a dokumenty s víc než 100 vektory v indexu (úklid starých částí je pak jen částečný).
- Kvalita vyhledávání na reálně velkém korpusu; ověřen je jen mechanismus (filtry, pořadí, latence) na 3 textech a 2 PDF.
- Skutečný tokenizer Titanu (odhad 2,05 znaku na token je z jednoho vzorku češtiny).
