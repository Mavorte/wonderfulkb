# be-validator-agent: zpracování dokumentů pro validační agent

Tady je všechno, co stojí za čtecím API pro Wonderful validační agent: klasifikace dokumentů, vektory, podpisy, pipeline, API, měření a referenční agent. **Předávka pro Wonderful je v [HANDOVER.md](HANDOVER.md).** Kontrakt API je v [../be-document-processing/contracts/openapi-validator-agent.yaml](../be-document-processing/contracts/openapi-validator-agent.yaml) (popis [../be-document-processing/VALIDATOR-AGENT.md](../be-document-processing/VALIDATOR-AGENT.md)), datový kontrakt mezi moduly v [docs/validator-agent-storage.md](docs/validator-agent-storage.md).

Stav k 19. 10. 2026 (večer): moduly jsou napsané a otestované samostatně (255 testů bez AWS zelených podle auditu), Agent API je nasazené v AWS (`wonderfulkb-agent-api`), pipeline zpracovala jen část datasetu. Nic z toho nebylo ověřeno na produkčních datech, jen na syntetických.

## Kde co je
| Složka | Co to je | Poznámka |
|---|---|---|
| [HANDOVER.md](HANDOVER.md) | předávka: adresy, klíč, co agent potřebuje, ověřené limity | začněte tady |
| [docs/wonderful-validator-agent.md](docs/wonderful-validator-agent.md) | návod pro Wonderful agenta: tři volání, nástroje, návrh promptu | |
| [docs/validator-agent-storage.md](docs/validator-agent-storage.md) | datový kontrakt: tabulka, S3 klíče, vektory | závazné rozhraní mezi moduly |
| [docs/validator-agent-audit.md](docs/validator-agent-audit.md) | nezávislý audit modulů a jeho nálezy | co ještě nesedí |
| [docs/validator-agent-privacy.md](docs/validator-agent-privacy.md) | podpisy neukládáme čitelně: šifrování, redakce, migrace | návrh a knihovna, nic nemigrováno |
| [api/](api/README.md) | Agent API (tři volání), AWS Lambda + SAM šablona | nasazeno |
| [pipeline/](pipeline/README.md) | PDF → text, stránky, štítek, vektory, podpisy → řádek analýzy | zatím se spouští ručně |
| [classify/](classify/README.md) | štítek, popis a jistota dokumentu (pravidla + model) | |
| [embed/](embed/README.md) | embeddingy (Titan) a zápis/čtení S3 Vectors | |
| [signatures/](signatures/README.md) | detekce podpisů, role, hash kopie, šifrované výřezy | detekce je neúplná |
| [privacy/](privacy/README.md) | šifrování výřezů (KMS), náhled, redakce | zatím mimo pipeline |
| [eval/](eval/README.md) | pravda a měření end-to-end po skupinách | |
| [dataset/](dataset/README.md) | nahrání 20 syntetických případů přes ingest | |
| [dedup/](dedup/README.md) | stejný obsah ve více případech: index hashů, znovupoužití analýzy, `duplicate_of` | kód a testy; v AWS nasazuje se |
| [trigger/](trigger/README.md) | automatické spuštění pipeline po uploadu (DynamoDB Stream → fronta → worker) | kód a testy; v AWS nasazuje se |
| [ref-agent/](ref-agent/README.md) | referenční validační agent nad třemi voláními (demo, ukázková pravidla) | |
| [mock/](mock/README.md) | mock Agent API se syntetickými daty | |

## Co v repu není a proč
- **Vzorové dokumenty z hackathonového balíku** (PDF a jejich textové výpisy) a **ukázkové výstupy z nich**. Repozitář je veřejný. Skripty, které je potřebují (`classify/evaluate.py`, `embed/benchmark.py`, `eval/build_truth.py`, mock), čtou složku z proměnné `WONDERFULKB_SAMPLES_DIR`. Bez nich nefungují jen tyto skripty a mock s texty; testy jedou na fixturách.
- **Skutečné adresy API, číslo AWS účtu a klíče.** V textu jsou zástupné symboly (`<AGENT_API_BASE_URL>`, `<INGEST_API_BASE_URL>`, `<CASE_API_BASE_URL>`, `<ACCOUNT_ID>`, `<KMS_KEY_ID>`). Skutečné hodnoty se předávají mimo repozitář.
- **Obrázky a výstupy z měření redakce** (lokální soubory z `privacy/measure/`); jsou regenerovatelné.

## Spuštění testů
Každý modul má vlastní `requirements*.txt` a README s příkazem. Python 3.14; PyMuPDF jen `pip install --only-binary :all: pymupdf` a jen pro `signatures/`. Příklad: `cd api && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest`.
