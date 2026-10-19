# classify: klasifikace typu dokumentu

`classify_document(text, title, page_count) -> {label, label_status, description, confidence}` podle [be-validator-agent/docs/validator-agent-storage.md](../../../be-validator-agent/docs/validator-agent-storage.md). Stav: hotové a změřené na 16 vzorových textech (19. 10. 2026), do AWS se nic nenasazuje. Model plní `label` i `description` jedním voláním, viz níže.

## Co tu je
| Soubor | Účel |
|---|---|
| `taxonomy.yaml` | 14 typů dokumentů (popis, klíčové znaky, skupina 0x/1x/2–4/99) a pravidla pro rychlou klasifikaci. ID štítků jsou shodná s `infra/validator-agent-mock/seed.py`. K nim přibyly `faktura`, `dodatek_ke_smlouve`, `technicka_specifikace`, `jine` |
| `prompt.py` | znovupoužitelné kousky pro vizuální přepis: `build_label_prompt_section()`, `LABEL_OUTPUT_SCHEMA`, `parse_label_output()` |
| `rules.py` | pravidla: normalizace textu (bez diakritiky, malá písmena) a skórování v zónách `title` (prvních 300 znaků), `head` (2500) a `any` |
| `llm.py` | backendy `ConverseBackend` (Bedrock Converse) a `MantleBackend` (Qwen3 VL přes Mantle), omezení rychlosti, retry s backoffem |
| `classifier.py` | `classify_document` a `classify_document_detailed` (navíc `method`, `rule_label`, `candidates`, `usage`, `error`) |
| `evaluate.py` | vyhodnocení na `docs/vzorove-dokumenty/text/` |
| `tests/` | 29 testů bez AWS (mock klient, mock HTTP) |

## Jak to funguje (podle rozhodnutí uživatele z 19. 10. 2026)
`label` a `description` plní LLM, **jedním voláním** (štítek, popis z obsahu dokumentu a jistota klasifikace, ne OCR).

1. **Text bez LLM přepisu** (textová vrstva): zavolá se `classify_document(text, title, page_count)` až po přepisu. Model se volá **vždy**, i při jasné hlavičce, protože popis musí být z obsahu. Do promptu jde katalog typů a prvních 5000 + posledních 1500 znaků textu (označeného jako nedůvěryhodný vstup), teplota 0.
2. **Pravidla z hlavičky** už nic nenahrazují, jen potvrzují: pokud mají jistý štítek a model vrátí jiný, štítek zůstává modelu a jistota se omezí na 0,5 (`rule_label` je v `classify_document_detailed`). Pravidla navíc slouží jako záloha: když model po všech pokusech selže a pravidla mají jistý štítek, vrátí se ten (`method: rules`, generický popis typu a jistota z pravidel 0,6 až 0,92, nekalibrovaná). Bez jistého štítku se vrací `label: None`, `confidence: None` a chyba je v `["error"]`. Funkce nikdy nevyhazuje výjimku.
3. **Text bez textové vrstvy** (méně než 40 znaků po normalizaci): model se nevolá, vrací se `label: None`, `confidence: None` a popis, že typ se určí po vizuálním přepisu. `label` je v kontraktu volitelný.
4. **Vizuální přepis (sken)**: štítek a popis vrací **stejné volání** jako přepis. Pipeline do promptu vizuálního kroku vloží kousky z `classify.prompt` a odpověď prožene přes `parse_label_output`:

```python
from classify.prompt import build_label_prompt_section, LABEL_OUTPUT_SCHEMA, parse_label_output

prompt = ocr_prompt + "\n\n" + build_label_prompt_section()      # úloha + katalog typů + pravidla pro description a confidence
schema["properties"].update(LABEL_OUTPUT_SCHEMA["properties"])      # label (enum z taxonomie), description, confidence
schema["required"] += LABEL_OUTPUT_SCHEMA["required"]
...
labelled = parse_label_output(model_json)   # {label, label_status, description, confidence}
```

`parse_label_output` ověří odpověď: neznámý štítek se změní na `jine`, jistota se ořízne do 0 až 1 (nečíselná je `None`), `label_status` je `predicted`. Sekce promptu říká, že `confidence` je jistota klasifikace, ne OCR. U vizuálního přepisu je dobré pole `label` / `description` / `confidence` dát do odpovědi až za přepis, aby model nejdřív dočetl stránku (v textovém klasifikátoru to je jedna odpověď, tam na pořadí nezáleží).

Název souboru (`title`) se ke klasifikaci **nepoužívá**, ani v pravidlech, ani v promptu (hlídá to test).

**Backendy.** Výchozí je Converse s `eu.anthropic.claude-haiku-4-5-20251001-v1:0` (odpověď vynucená nástrojem `classify` s `enum` štítků). Alternativa je Mantle (`CLASSIFY_BACKEND=mantle`, výchozí model `qwen.qwen3-vl-235b-a22b-instruct`, `https://bedrock-mantle.eu-central-1.api.aws/v1/chat/completions`, SigV4 přes `botocore`, bez dalších závislostí; JSON se žádá v promptu a parsuje se). Model se mění přes `CLASSIFY_MODEL_ID`, v kódu `classify_document(..., backend=llm.MantleBackend())`.

**Omezení rychlosti.** Tým sdílí 50 požadavků/min. Proces drží vlastní odstup mezi voláními (`CLASSIFY_MAX_RPM`, výchozí 30) a `ThrottlingException`, `ServiceUnavailableException`, `ModelTimeoutException`, `ModelNotReadyException`, `InternalServerException`, časové limity a HTTP 429 / 5xx z Mantle se opakují nejvýš 6krát s exponenciálním backoffem (2, 4, 8, 16, 30 s, s jitterem). Limiter je jen v rámci jednoho procesu; více paralelních workerů musí limit dělit.

## Jak spustit
Python 3.14, závislosti `boto3`, `pyyaml`, `pytest` (`requirements.txt`; PyMuPDF se nepoužívá). Stroj je nemá předinstalované, vytvoř venv:

```bash
python3 -m venv /tmp/classify-venv && /tmp/classify-venv/bin/pip install -r requirements.txt
```

Použití z kódu (z adresáře `infra/validator-agent`):

```python
from classify import classify_document
classify_document(text, title, page_count)   # AWS přihlášení z prostředí, např. AWS_PROFILE=hackathon
```

Testy (bez AWS):

```bash
cd infra/validator-agent && /tmp/classify-venv/bin/python -m pytest classify/tests -q
```

Vyhodnocení na vzorcích (`aws sso login --profile hackathon` jen pro režimy s modelem):

```bash
cd infra/validator-agent/classify
/tmp/classify-venv/bin/python evaluate.py --rules-only        # jen pravidla, bez AWS (model se nevolá)
AWS_PROFILE=hackathon /tmp/classify-venv/bin/python evaluate.py                      # Haiku 4.5, Converse
AWS_PROFILE=hackathon /tmp/classify-venv/bin/python evaluate.py --backend mantle     # Qwen3 VL, Mantle
AWS_PROFILE=hackathon /tmp/classify-venv/bin/python evaluate.py --show-description   # vypíše i popisy
AWS_PROFILE=hackathon /tmp/classify-venv/bin/python evaluate.py --strip-head 600     # bez nadpisu
```

Očekávaný typ `evaluate.py` odvozuje z číselného prefixu názvu souboru jen pro vyhodnocení.

## Modely a region (zjištěno 19. 10. 2026)
- `aws bedrock list-inference-profiles` ukazuje aktivní `eu.anthropic.claude-haiku-4-5-20251001-v1:0`, `…sonnet-4-5-…`, `…opus-4-5-…` a také profily 5 / 5.5. Podle pravidel týmu se modely 5.5 nepoužívají.
- **Profil `eu.anthropic.claude-haiku-4-5-…` směruje mimo Frankfurt.** `aws bedrock get-inference-profile` uvádí popis „Routes requests to Anthropic Claude Haiku 4.5 in eu-central-1, eu-north-1, eu-south-1, eu-south-2, eu-west-1 and eu-west-3“, a `get-foundation-model` pro Haiku 4.5 vrací jen `INFERENCE_PROFILE` (žádná přímá inferenční cesta ve Frankfurtu). Požadavek tedy může obsloužit kterýkoli z těchto šesti EU regionů a odpověď neříká, který. To je v rozporu s požadavkem `be-document-processing/README.md` „výhradně Frankfurt“ (tam proto Haiku není nakonfigurovaný). Pokud musí zpracování zůstat ve Frankfurtu, použij Mantle s Qwen3 VL.
- **Qwen3 VL přes Mantle** (`qwen.qwen3-vl-235b-a22b-instruct`) je v `list-foundation-models` Runtime pro Frankfurt vidět jen jako textové Qwen3 modely, ale endpoint `bedrock-mantle.eu-central-1.api.aws` model obsluhuje a volání z mého přihlášení fungovalo. Endpoint je regionální, takže zpracování zůstává ve Frankfurtu (to jsem prověřil jen z podoby URL a dokumentace `be-document-processing`, nikoli nezávisle).

## Naměřená přesnost (16 vzorových textů ze dvou případů, 19. 10. 2026)
Všude 15 dokumentů s textem a 1 sken bez textu (Solom protokol, 1 slovo, model se nevolá). Hodnotí se jen `label`, popisy jsem prohlédl namátkou (viz níže).

| Režim | Štítek správně | Latence volání (medián / max) | Tokeny celkem |
|---|---|---|---|
| Haiku 4.5, Converse (výchozí) | 14/15 | 2,8 s / 3,7 s | 83 339 |
| Qwen3 VL 235B, Mantle | 14/15 | 3,0 s / 5,3 s | 78 590 |
| Jen pravidla (`--rules-only`, bez modelu) | 14/14 s textem (jediné, co pravidla rozhodla) | zanedbatelná | 0 |

- Obě varianty udělaly **stejnou jedinou chybu**: Solom objednávka (`10_…objednávka`, sken s 22 slovy, jen adresa a razítko) dostala `jine` s jistotou 0,30. To je správné chování při chybějícím textu (a jistota to říká), jen chybí očekávaný štítek `objednavka`; vyřeší to až vizuální přepis.
- U 14 dokumentů, kde pravidla rozhodla, se s nimi model shodl vždy (14/14).
- Správné štítky mají jistotu 0,95 až 0,98, takže jistota modelu mezi nimi moc nerozlišuje (0,3 u nečitelného dokumentu je jediný nízký údaj).
- Z první verze, kdy pravidla ještě rozhodovala sama: po odříznutí nadpisu (`evaluate.py --strip-head 600`) pravidla se starým prahem 7 bodů chybně označila VOP za smlouvu o úvěru, proto je práh 9 bodů (hlídá to test). Nyní, kdy pravidla štítek jen potvrzují, to ovlivní nanejvýš zálohu při výpadku modelu.
- Popisy (1 až 2 věty česky, s čísly smluv, stranami a předměty) jsou z obsahu dokumentu. Namátkou jsem je porovnal se zdrojovým textem; je vidět, že přebírají nesrovnalosti ze vzorků (např. u zajišťovacího převodu „FIRESTA-Fišer, rekonstrukce, stavby a.s.“), což je správně. Úplná kontrola popisů nebyla provedena: u Qwen popisu úhrady („ve prospěch Stavby Fišer a.s.“) není z výpisu jisté, že jde o příjemce platby.

## Co není ověřené
- **Pravidla jsem psal s přečtenými vzorky v ruce**, takže 14/14 v režimu `--rules-only` je spíš kontrola, že pravidla sedí na ty samé dokumenty, ne odhad přesnosti na nových. Nezávislý údaj je jen výsledek modelu (ten vzorky při návrhu neviděl). Protože pravidla jen potvrzují a slouží jako záloha, jejich přesnost už štítek neurčuje.
- **Vzorků je málo** (16 dokumentů, 2 případy, 10 typů). Typy `faktura`, `dodatek_ke_smlouve`, `technicka_specifikace` a `jine` nemají vzorový dokument; jejich pravidla jsou odhad z běžné podoby těchto dokumentů a nikdy nebyla vyzkoušena na skutečném textu. Faktury ve vzorcích chybí úplně.
- **Jistota** z pravidel není kalibrovaná, jistota z modelu je jeho vlastní odhad. Nezkoumal jsem, jak dobře odpovídá skutečné chybovosti.
- **Skeny** (bez textové vrstvy) klasifikovat nelze, dokud neproběhne OCR. Modul čeká na text z OCR od Kryštofa; texty z OCR (jiné formátování, chyby rozpoznání) jsem nezkoušel. Klasifikaci z obrázku stránky tento modul sám neprovádí; dělá ji vizuální krok pipeline pomocí `classify.prompt` (viz výše).
- **Dva dokumenty v jednom PDF** (např. `10_…Objednávka + TS`) dostanou jeden štítek, tady `objednavka`. Dělení balíku na dokumenty tu není.
- Zátěž a chování při opravdovém omezení rychlosti: retry je otestován mock klientem, ne reálným `ThrottlingException` z Bedrocku. Na vzorcích žádné omezení nenastalo.
- Jedno volání modelu na dokument je ~5 500 tokenů (u obou modelů); u velkých balíků 20 případů počítej s limitem 50 požadavků/min a se spotřebou do hodnocení.
- Sdílený krok s vizuálním přepisem (`classify.prompt`) je jen otestován jednotkově (mock); s reálným modelem a obrázkem jsem ho nespouštěl. Kvalita štítku a popisu ve spojeném volání (přepis + štítek) není změřena.
- Qwen přes Mantle: JSON se vynucuje jen promptem (žádný nástroj ani schéma); na vzorcích vždy platný, ale na jiných textech to jisté není. Mantle jsem nezatěžoval, retry při HTTP 429 je ověřen jen mockem.
