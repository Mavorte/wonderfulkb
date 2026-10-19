# Validační agent: vstupní API

Stav: **verze 0.4.0, API je implementované a nasazené** (implementace, předávka a návod pro agenta jsou v [../be-validator-agent](../be-validator-agent/README.md)). Formální popis: [contracts/openapi-validator-agent.yaml](contracts/openapi-validator-agent.yaml).

Wonderful agent, který podle pravidel validuje a rozhoduje, nedostává data v těle požadavku. Bere si je čtyřmi oddělenými voláními (nástroji agenta). Textová data jsou malá a potřebuje je vždy. Vektory jsou velké a agent je potřebuje jen tehdy, když pravidlo vyžaduje srovnání (podobnost dokumentu, kopie podpisu). Proto se **agentovi nedávají surové vektory, ale výsledek hledání** (`neighbors`, `matches`).

| # | Volání | Zdroj | Kdy agent volá |
|---|---|---|---|
| 0 | `GET /cases/{case_id}/documents` | tabulka dokumentů | na začátku, zjistí `document_id` a stav zpracování |
| 1 | `GET /cases/{case_id}/documents/{document_id}` | výstup OCR (tabulka dokumentů) | vždy, pro každý dokument case |
| 2 | `GET /cases/{case_id}/documents/{document_id}/vectors` | S3 Vectors, indexy textu a obrazu | ověření typu dokumentu, podobné dokumenty |
| 3 | `GET /cases/{case_id}/documents/{document_id}/signatures` | detekce podpisů + S3 Vectors, index podpisů | pravidla na podpisy |

Společné s ostatními službami: `x-api-key`, JSON UTF-8, časy ISO 8601 UTC, chyby `{"error": "popis"}` (`400`, `403`, `404`, `409`, `5xx`), region `eu-central-1`, prefix a tag `wonderfulkb`. `case_id` a `document_id` jsou stejné jako v ingest API (`document_id` = `blob_id`).

## Uložení dat (rozhodnutí z podkladů)
- **Řádek patří dokumentu**, klíč `case_id` + `document_id`, ne případu (případ má víc dokumentů). Navazuje na tabulku `wonderfulkb-uw-documents`.
- **Vektory se neukládají do tabulky.** 1024 floatů je kolem 8 KB na vektor, tabulku by zbytečně nafoukly. Leží v **S3 Vectors**, tabulka má jen odkazy (klíče vektorů).
- **Text po částech, obraz po stránkách.** Jeden vektor na celý vícestránkový dokument je příliš hrubý a Titan Text V2 zvládne omezený počet tokenů, delší přepis se musí dělit. Vektor textu = jeden na část (chunk), vektor obrazu = jeden na stránku.
- **U každého vektoru model a verze.** Po změně modelu jsou staré vektory k ničemu a nemíchají se: **jeden index na typ vektoru** (vytvořené 19. 10. 2026 v bucketu `wonderfulkb-vectors`, eu-central-1: `wonderfulkb-text`, `wonderfulkb-image`, `wonderfulkb-signatures`, všechny 1024 dimenzí, cosine, ENHANCED). Při změně modelu nebo dimenze se index zakládá znovu, proto `model` a `model_version` jdou i do metadat vektoru.
- Filtrovatelná metadata vektoru: `case_id`, `document_id`, `page`, `label`, `verified`. **Sjednotit:** session s indexy doporučuje `doc_id`, kontrakt i ingest používají `document_id`. Dlouhý text jen jako nefiltrovatelná metadata. Používat bucket v režimu `ENHANCED`, jinak filtrovaný dotaz může vrátit méně než top-K (viz architektura-aws-scale.md).
- **Ověřeno 19. 10. 2026:** vector bucket, index a dotaz s filtrem `verified = true` ve Frankfurtu fungují (aws-ucet-hackathon.md).
- Poznámka k podkladu: tvrzení „DynamoDB nemá vektorový index" je zastaralé, má ho od srpna 2026 (dynamodb-s3-vectors-vs-postgres.md). Rozhodnutí týmu je přesto S3 Vectors a pro hackathon stačí i numpy kosinová podobnost nad vektory v paměti.

## 0. Seznam dokumentů case

`GET /cases/{case_id}/documents` (`listCaseDocuments`): stručný přehled bez textu, řazený podle `document_id`. Parametry `limit` (1 až 100, výchozí 50), `next_token` (neprůhlivý, `null` na poslední stránce), `processing_status` (filtr, např. `completed`).

```json
{ "case_id": "…", "next_token": null,
  "documents": [
    { "document_id": "d2f4a1", "title": "0_Form_Smlouva.pdf", "label": "smlouva_o_uveru",
      "label_status": "verified", "processing_status": "completed", "page_count": 4 } ] }
```

Agent zpracovává jen `completed` a `partial`. Ostatní stavy (`awaiting_upload`, `queued`, `processing`, `failed`) nemají text ani vektory a detail vrací `409`. Cesta je stejná jako `listDocuments` v Ingest API, ale jiná služba a jiná odpověď (štítek a stav OCR místo údajů o uploadu).

## 1. Dokument (text a metadata)

`GET /cases/{case_id}/documents/{document_id}`

```json
{
  "case_id": "7b0e5c1a-3f42-4d8e-9a61-2c5d8e4f1b90",
  "document_id": "d2f4…",
  "title": "0_Form_Smlouva.pdf",
  "label": "smlouva_o_uveru",
  "label_status": "predicted",
  "description": "Smlouva o úvěru č. 170170/25 mezi … a Stavby Fišer s.r.o.",
  "text": "SMLOUVA O ÚVĚRU …",
  "confidence": 0.93,
  "page_count": 4,
  "processing_status": "completed"
}
```

| Pole | Význam | Poznámka |
|---|---|---|
| `case_id`, `document_id` | identifikátory | UUID z `POST /cases`, `blob_id` z uploadu |
| `title` | název | původní název souboru; **ke klasifikaci se nepoužívá** |
| `label` | štítek, typ dokumentu | hodnoty z `taxonomy.yaml`; `null`, dokud není klasifikováno |
| `label_status` | `predicted` / `verified` | strojový štítek není ověřený, dokud ho nepotvrdí člověk |
| `description` | popis | krátké shrnutí obsahu |
| `text` | text dokumentu | celý přepis, strany oddělené `\f` |
| `confidence` | jistota 0 až 1 | jistota klasifikace štítku; `null`, pokud ji zdroj neposkytuje |

`404` neexistující case nebo dokument. `409` OCR ještě nedoběhlo (v těle aktuální stav). U `partial` vrací text úspěšných stran a `pages_failed`.

## 2. Vektory dokumentu

`GET /cases/{case_id}/documents/{document_id}/vectors`

```json
{
  "case_id": "…", "document_id": "…",
  "text_vectors": [
    { "chunk_id": "c0", "page_from": 1, "page_to": 1, "model": "amazon.titan-embed-text-v2:0", "model_version": "v2", "dimension": 1024, "values": [0.012, …] } ],
  "image_vectors": [
    { "page": 1, "model": "cohere.embed-v4:0", "model_version": "v4", "dimension": 1024, "values": [0.044, …] } ],
  "neighbors": [ { "document_id": "…", "label": "smlouva_o_uveru", "score": 0.91 } ]
}
```

- Parametry: `include=text|image`, `include_values=false` (jen metadata, bez čísel), `similar_to_verified=N` (vrátí `neighbors`: N nejbližších **ověřených** dokumentů podle filtru `verified = true`).
- Dokument bez vektorů vrací prázdná pole, ne chybu.
- Agent by měl používat `neighbors` s `include_values=false`. Surové vektory se do kontextu LLM nehodí (desítky kB).

## 3. Podpisy

`GET /cases/{case_id}/documents/{document_id}/signatures`

Čtyři kroky, každý má vlastní místo:

| Krok | Co | Kde |
|---|---|---|
| 1. Detekce | kde podpis je | Textract `AnalyzeDocument` / `StartDocumentAnalysis` s funkcí `SIGNATURES` (bbox + jistota); záloha vision LLM |
| 2. Přiřazení | čí je (role) | nejbližší textové bloky z OCR („Za dlužníka", jméno, funkce) podle polohy |
| 3. Pravidla | chybí / mimo místo | ve Wonderful (ne vektory); my dodáváme data z tohoto volání |
| 4. Srovnání | kopie, odlišný podpis | S3 Vectors (index podpisů) + perceptuální hash |

```json
{
  "case_id": "…", "document_id": "…",
  "signatures": [
    { "signature_id": "sig_01", "page": 3, "bbox": [0.12, 0.71, 0.38, 0.79],
      "detector": "textract", "detection_score": 65.6,
      "role": "borrower", "role_source": "nearest_text", "role_evidence": "Za dlužníka",
      "crop_url": "https://…", "phash": "c3a1…",
      "copy_suspicion": { "level": "none", "matches": [] },
      "similar_signatures": [ { "signature_id": "…", "document_id": "…", "score": 0.82 } ] } ]
}
```

- **`signatures: []` je validní odpověď** („nic nenalezeno"), pravidlo „podpis chybí" ji musí rozlišit od chyby.
- `detection_score` je orientační skóre Textractu (rozptyl 11,9 až 65,6 na dvou vzorcích), **ne kalibrovaná pravděpodobnost**. Agent ho nemá používat jako práh rozhodnutí, nízké skóre jen zvýšit prioritu pro člověka. Pole se jmenuje `detection_score`, ne `confidence`, aby se nepletlo s jistotou z volání 1.
- `copy_suspicion`: skoro identický podpis v různých dokumentech je podezřelý (skutečné podpisy se vždy trochu liší, přesná kopie může být vložený obrázek). Počítá se perceptuálním hashem nebo pixelovým porovnáním, ne embeddingem. `level`: `none` / `suspected`.
- `similar_signatures` (jen s `match_client=true`): nejbližší podpisy téhož klienta z indexu. Obecný embedding není model pro ověřování podpisů, takže je to jen nápověda pro člověka.
- `crop_url`: předpodepsaný výřez podpisu (300 s) pro lidskou kontrolu. **Každý nález odkazuje na stranu a výřez.**
- **Co se neslibuje:** žádný krok neověřuje pravost podpisu. Výstup je „přítomnost, přiřazená role, podezření na kopii".

## Co agent z toho skládá

Doporučený postup: seznam (0) → pro každý dokument detail (1) → vektory (2) a podpisy (3) jen u pravidel, která je potřebují. U vektorů vždy `include_values=false&similar_to_verified=N`, u podpisů `include_vectors=false`.

```
case_id ──▶ (1) text + štítek + jistota        → obsah, úplnost, shoda entit
        ├─▶ (2) neighbors                      → ověření typu dokumentu
        └─▶ (3) podpisy, role, copy_suspicion  → pravidla na podpisy (kontrola 13 v kontroly-a-entity.md)
```

## Změny oproti 0.1.0
Jen aditivní: nové volání `listCaseDocuments`, tag `signatures`, odpověď `400` u všech volání, popisy a příklady odpovědí přímo ve spec (aby agent z ní poznal, kdy co volat a jak číst prázdné odpovědi), schéma `ProcessingStatus`. Stávající schémata se nezměnila.

## Otevřené otázky
1. **Odkud se bere `label`, `description`, `confidence`?** Kryštofova služba (`be-document-processing`) štítek ani popis nevrací a její VLM dává `confidence: null`. Navrhuju: `confidence` = jistota klasifikace štítku (jistota polí zůstane u extrakce).
2. **Kdo a kdy plní S3 Vectors** (indexy dokumentů a podpisů): Kryštofova pipeline po OCR, nebo samostatný krok? Do té doby vrací volání 2 a 3 prázdná pole.
3. **Modely a dimenze:** indexy mají pevně 1024 dimenzí. Text Titan V2 (1024) sedí. Obraz: Titan Multimodal Embeddings (`amazon.titan-embed-image-v1`) by měl jít s výstupem 1024 (z paměti, ověřit v dokumentaci); Cohere Embed v4 má výchozích 1536 a vyžadoval by výstup 1024 nebo nový index. Že Kryštof doplňuje Titan Multimodal, jsem v kódu nenašel, potvrdit s ním. Podpis zatím bez modelu, index už existuje.
4. **Textract SIGNATURES:** funguje ve Frankfurtu (ověřeno na 2 PDF), ale zatím není ověřeno, že nalezené bloky jsou podpisy, ani že nic nechybí. Vizuální kontrola výřezů je rozpracovaná.
5. **Vrstva API:** samostatná Lambda `wonderfulkb-agent-api` (čte jiné tabulky a S3 Vectors) místo rozšíření `wonderfulkb-case-client`. Souhlas?

## Změny od verze 0.2.0 (0.3.0)
- **Volání 3 má povinné pole `status`** (`completed` / `not_run` / `failed`). Prázdné `signatures` je „nic nenalezeno" jen při `completed`; při `not_run` podpisy ještě nikdo nehledal.
- **`copy_suspicion.level` má novou hodnotu `not_checked`:** porovnání napříč dokumenty se nepočítalo. `none` znamená, že proběhlo a nic nenašlo.
- **Enum `detector`** je `textract`, `vision_llm`, `page_images`, `label_anchored`, `vector_strokes`; u každého nálezu je zdroj, který ho našel.
- **`similar_signatures` je zatím vždy prázdné** (index podpisů je prázdný). Plánovaný význam: podobné podpisy téhož klienta napříč případy.
- **`neighbors` jsou zatím prázdné:** vznikne až z lidsky ověřených dokumentů (`label_status = verified`).
- Detekce podpisů je neúplná; viz [be-document-processing/docs/signatures-eval](docs/signatures-eval/README.md) a [předávka](../be-validator-agent/HANDOVER.md).

## Změny od verze 0.3.0 (0.4.0)
- **Volání 1 (dokument):** nové `duplicate_of` (jiné případy se stejným obsahem, `[{case_id, document_id, label}]`) a `duplicate_relevant` (true jen u individuálních dokumentů; šablony jako VOP se neoznačují). Chyba čtení indexu hashů pole vynechá, nikdy nevrací 5xx.
- **Volání 3 (podpisy):** `crop_url` už se nevrací. U každého podpisu je `preview_url` (zkreslený náhled, 300 s), `reveal_path` a `crop_available`. Čitelný podpis dává jen `GET …/signatures/{signature_id}/image` (dešifruje výřez, `Cache-Control: no-store`, s auditem).
- **Ingest:** odpověď uploadu má volitelné `also_in` (stejný obsah v jiných případech); viz `be-intake/openapi-ingest.yaml`.
