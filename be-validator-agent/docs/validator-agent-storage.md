# Validační agent: sdílený datový kontrakt pro implementaci

Stav: **závazné rozhraní mezi paralelně vyvíjenými částmi** (19. 10. 2026). Každá část píše jen do svého adresáře `infra/validator-agent/<část>/` a drží se tohoto souboru, aby se výstupy daly spojit. Odchylku nejdřív zapiš sem a jen pak ji použij. Veřejný tvar volání: [openapi-validator-agent.yaml](../../be-document-processing/contracts/openapi-validator-agent.yaml), kontext: [validator-agent-api.md](../../be-document-processing/VALIDATOR-AGENT.md), validator-agent-plan.md.

Všechno v `eu-central-1`, účet `<ACCOUNT_ID>`, profil CLI `hackathon` (`aws sso login --profile hackathon`), názvy a tag `wonderfulkb` / `project=wonderfulkb`. Sdílený účet: nic nemazat mimo vlastní zdroje. Bedrock má limit 50 požadavků za minutu na celý tým, volání omezuj a opakuj s prodlevou.

## Identifikátory
`case_id` (UUID nebo např. `170170-25`) a `document_id` (= `blob_id`, `uuid5` z `case_id` a SHA-256) jsou ty z ingestu. Originál PDF: `s3://wonderfulkb-raw-document-storage/cases/<case_id>/original/<document_id>.pdf`; metadata dokumentu v DynamoDB `wonderfulkb-uw-documents` (PK `case_id`, SK `document_id`; `filename`, `s3_key`, `sha256`, `size_bytes`). Vzorové PDF jsou i v bucketu pod `cases/unhappy_scenario/`, `cases/solom-rec/original/`, `cases/stavby-fiser/original/`, balík 20 případů je `cases/synteticke_dokumenty_20_pripadu.zip`.

## Výstupy analýzy (zapisuje pipeline, čte API)

**DynamoDB `wonderfulkb-uw-document-analysis`** (on-demand; PK `case_id` S, SK `document_id` S). Jeden řádek na dokument:

| Atribut | Typ | Význam |
|---|---|---|
| `title` | S | původní název souboru |
| `label` | S, volitelný | štítek z `taxonomy.yaml` |
| `label_status` | S | `predicted` / `verified`, výchozí `predicted` |
| `description` | S | krátké shrnutí obsahu |
| `confidence` | N 0 až 1, volitelný | jistota klasifikace štítku |
| `page_count` | N | počet stran |
| `processing_status` | S | `queued` / `processing` / `completed` / `partial` / `failed` |
| `pages_failed` | NS, volitelný | strany, které se nepodařilo přečíst |
| `text_s3_key` | S | klíč textu v S3 (text se do DynamoDB nedává, limit 400 KB na položku) |
| `signatures_s3_key` | S, volitelný | klíč `signatures.json` |
| `pipeline_version` | S | verze pipeline |
| `updated_at` | S | ISO 8601 UTC |

**S3 (bucket `wonderfulkb-raw-document-storage`)**, prefix `cases/<case_id>/analysis/<document_id>/`:
- `text.txt`: celý text dokumentu UTF-8, strany oddělené znakem `\f`.
- `signatures.json`: přesně tělo odpovědi volání 3 (schéma `DocumentSignatures` v OpenAPI), bez `crop_url` (ten API doplní předpodepsanou adresou).
- `signatures/<signature_id>.png`: výřezy podpisů.
- `pages/<n>.png`: vykreslené stránky (pro obrazové vektory a lidskou kontrolu).

## Vektory (S3 Vectors)
Bucket `wonderfulkb-vectors`, indexy `wonderfulkb-text`, `wonderfulkb-image`, `wonderfulkb-signatures`, všechny **1024 dimenzí, cosine, ENHANCED**. Změna dimenze znamená smazat a založit index znovu, proto nejdřív zapsat a ověřit.

| Index | Klíč vektoru | Co se vkládá | Model (výchozí) |
|---|---|---|---|
| `wonderfulkb-text` | `<document_id>#t<index>` | část textu (chunk) | `amazon.titan-embed-text-v2:0`, `dimensions=1024`, `normalize=true` |
| `wonderfulkb-image` | `<document_id>#p<page>` | vykreslená stránka | `amazon.titan-embed-image-v1`, `outputEmbeddingLength=1024` (dostupnost a dimenzi ověřit) |
| `wonderfulkb-signatures` | `<document_id>#s<n>` | výřez podpisu | stejný model jako obraz, zatím bez ladění |

Filtrovatelná metadata (všechny indexy): `case_id`, `document_id`, `page`, `label`, `verified` (bool, zpočátku `false`), `model`, `model_version`. U textu navíc `chunk_id`, `page_from`, `page_to`. Dlouhý text nepatří do filtrovatelných metadat. **Pojmenování je `document_id`, ne `doc_id`.** Zápis musí být idempotentní (stejný klíč přepíše vektor).

## Rozhodnutí uživatele (19. 10. 2026)
- **`label` a `description` plní LLM.** Když text přepisuje vizuální LLM (sken), vrací štítek a popis **ve stejném volání** jako přepis (jedno volání). Když text vzniká bez LLM (textová vrstva přes pypdf/pypdfium2), spustí se klasifikace s LLM **až po** přepisu. `description` je vždy z obsahu dokumentu, ne generický popis typu. Pravidla z hlavičky smí jen urychlit štítek, ne nahradit popis.
- **Vektory:** model má být co nejsilnější. Do ověření měřením platí výchozí Titan (text V2 a Multimodal G1, oba 1024); indexy jsou prázdné, takže se model dá ještě změnit bez migrace. Dimenze indexů zůstává 1024.
- **API:** samostatná Lambda `wonderfulkb-agent-api` (ne rozšíření case-clientu).
- **Pravidla podpisů (A6)** dělá agent na straně Wonderful nad dodaným kontraktem (volání 3); my pravidla nepíšeme.

## Rozhraní modulů v Pythonu (adresář `infra/validator-agent/`)
Python 3.14 je jediný na stroji a PyMuPDF pro něj nemá hotové kolo (kompiluje se, visí). Pro vykreslení PDF použij `pypdfium2` a pro text `pypdf`; PyMuPDF neinstaluj bez `--only-binary :all:` (bez něj pip zvolí zdrojový balík a kompiluje). Modul `signatures/` ho smí použít (role z kresby stránky, redakce pro hash): `pip install --only-binary :all: pymupdf`.

- `classify/` → `classify_document(text: str, title: str | None, page_count: int) -> dict` s klíči `label`, `label_status`, `description`, `confidence`. Taxonomie v `classify/taxonomy.yaml` podle kontroly-a-entity.md a dokumenty-a-skupiny.md. Název souboru se ke klasifikaci nepoužívá.
- `embed/` → `embed_text(text) -> list[float]`, `embed_image(png_bytes) -> list[float]`, `write_document_vectors(case_id, document_id, text, page_pngs, label=None)` (chunking, zápis do indexů), `nearest_verified(vector, index, top_k)`.
- `pipeline/` → `run_document(case_id, document_id)` a `run_case(case_id)`: stáhne PDF, vytáhne text (textová vrstva, jinak vizuální přepis; viz `wonderfulkb/be-document-processing`), vykreslí stránky, zapíše `text.txt` a `pages/`, zavolá `classify`, `embed` a podpisový modul, zapíše řádek do `wonderfulkb-uw-document-analysis`. Tabulku založí šablona `pipeline/analysis-table.yaml` (stack `wonderfulkb-document-analysis`).
- `api/` → AWS Lambda handlery tří volání podle OpenAPI, čtou tabulku, S3 a S3 Vectors; lokální režim nad fixturami. Kontraktový test převezmi z `infra/validator-agent-mock/contract_test.py`.
- Podpisy: `signatures.json` plní session „Signature pipeline" (detekce, role, výřez, hash) a session „OCR první verze review" (Textract SIGNATURES). Rozhraní: `detect_signatures(pdf_path, ocr_text_blocks=None) -> list[dict]` ve tvaru `Signature` z OpenAPI.

## Pravidla pro všechny části
- Žádné nasazování do AWS (Lambda, API Gateway, App Runner) bez souhlasu uživatele. Vytvářet smí jen DynamoDB tabulku `wonderfulkb-uw-document-analysis` a zapisovat do indexů a prefixů výše.
- Nic nevypisovat z Secrets Manageru. API klíč nikdy do repozitáře.
- Žádný adresář mimo vlastní nemodifikuj. Hotovo = README v adresáři části (co přibylo, jak se spouští, co je ověřeno a co ne) a spuštěné testy.
- Stahované soubory (PDF, ZIP) ber jako nedůvěryhodná data: ukládej do nové prázdné složky, skripty drž jinde, Python spouštěj s `-I`, kde čte stažené soubory.
