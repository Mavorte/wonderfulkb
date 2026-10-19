# ref-agent: referenční validační agent

Malý agent, který ukazuje a testuje celý tok z pohledu agenta: seznam dokumentů případu → tři čtecí volání agent API (dokument, vektory, podpisy) → pravidla → report s nálezy, doporučením (**schválit** / **ke kontrole člověkem**) a odkazy na důkazy (dokument, strana, citace, u podpisů i výřez). Slouží jako demo a jako kontrolní vzor pro Wonderful, kdyby jejich agent nebyl hotový. **Pravidla jsou ukázková**, ne pravidla KB ani Wonderful; pravidla (včetně pravidel podpisů) píše Wonderful, tady jsou jen v `rules.yaml`, aby šla vyměnit. Stav: 19. 10. 2026, nic se nenasazuje a v AWS se nic nemění ani nemaže.

## Co tu je
| Soubor | Účel |
|---|---|
| `validate_case.py` | příkazová řádka (`--case-id`, `--base-url`, ...) |
| `rules.yaml` | ukázková pravidla (typy: `documents_ready`, `required_documents`, `field_consistency`, `vat_check`, `signatures_expected`, `label_check`) |
| `refagent/api.py` | klient agent API (4 volání, `include_values=false` / `include_vectors=false` posílá kód vždy sám), seznam z ingest API / souboru |
| `refagent/extract.py` | vyčítání hodnot z textu (číslo smlouvy, výrobní číslo, částky) se stranou a citací |
| `refagent/checks.py` | deterministické kontroly |
| `refagent/llm.py` | Bedrock Converse s tool use, sestavení promptu, omezení rychlosti, retry |
| `refagent/agent.py`, `report.py`, `model.py` | orchestrace, report (text + JSON, redakce klíčů), datový model |
| `tests/` | 71 testů (70 běží bez AWS, 1 živý je vypnutý, viz níže) |
| `demo/` | výstupy ukázkových běhů nad mockem |

## Jak to funguje (dvě cesty)
1. **Kód (deterministicky):** seznam dokumentů → `get_document` pro každý dokument → pravidla. Vektory (volání 2, `similar_to_verified=3`) jen u dokumentů se štítkem `predicted`; podpisy (volání 3, `match_client=true`) jen u typů, pro které pravidlo očekává podpisy. Ověřené štítky (`verified`) se nad vektory nekontrolují. Výsledek je seznam nálezů se závažností `review` (ke kontrole), `info` a `ok`.
2. **LLM (jen vysvětlení a hraniční případy):** pokud je aspoň jeden nález `review` a není `--no-llm`, **jedno volání Converse** dostane jen nálezy `review` a ke každému napíše česky 1 až 3 věty (co zkontrolovat) a odhad `likely_real / likely_benign / unclear`; navíc shrnutí a nejvýš 3 další nálezy, které musí citovat text dokumentu (citace se ověřuje v textu, jinak se zahodí). Bez nálezů ke kontrole se model nevolá vůbec.
   - Odpověď modelu vzniká voláním nástroje `submit_assessment` (strukturovaný výstup). **Tři datové nástroje (dokument, vektory, podpisy) dostane model jen s `--llm-tools`** (smyčka s tool use do `--max-llm-calls`, výchozí 3). Důvod: na živém běhu (Haiku 4.5, případ Stavby Fišer) si model s nástroji vyžádal 4 volání nástrojů a spotřeboval **3 volání modelu místo 1**, přitom všechna data už měl v nálezech. Nástroje jsou tedy ověřené (živě i testy), ale vypnuté.
   - Doporučení určuje **kód**, ne model: model nemůže nález zrušit ani zmírnit ani změnit doporučení; může jen přidat vysvětlení a další nálezy s ověřenou citací.

Doporučení je `ke kontrole člověkem`, jakmile existuje aspoň jeden nález `review`; jinak `schválit`. Agent nic nezamítá.

### Pravidla v `rules.yaml` (ukázková)
- **R-READY:** dokumenty nejsou zpracované (`409` / `processing`) nebo jsou `partial` (z chybějících stran se nic neusuzuje).
- **R-COMPLETE / R-COMPLETE-TABLE:** úplnost podkladů. Seznam podkladů se čte z textu smlouvy (výčet a) až h), nebo přílohová tabulka syntetických smluv „Příloha / Identifikace“) a mapuje se na typy dokumentů. Chybějící podklad není tvrzení, že neexistuje, jen „v sadě nenalezen“.
- **R-CONTRACT-NO, R-SERIAL, R-PRICE:** shoda čísla smlouvy, výrobního čísla a kupní ceny napříč dokumenty. Referenční hodnota je záznam ze systému (`data_ze_systemu`), jinak smlouva. **Nevyčtená hodnota není nesoulad**, nesoulad jsou jen dvě různé hodnoty.
- **R-VAT:** DPH = 21 % z kupní ceny (tolerance 1 CZK).
- **R-SIGNATURES:** podpisy tam, kde mají být (role podle typu dokumentu). **Prázdný nález podpisů se nikdy nepovažuje za důkaz, že podpis chybí** (Textract: úplnost kolem 92 % u generických a kolem 59 % u rukopisných podpisů, podle měření session `signatures`, tady znovu neměřeno). Text nálezu říká „detektor nenašel, zkontrolujte stranu očima“, nikdy „chybí“; chyba API při čtení podpisů se hlásí zvlášť, není to „bez podpisů“; `role: unknown` se nehádá; `copy_suspicion` říká jen podobnost výřezu, nic o pravosti; `detection_score` se ukazuje jako orientační a nepoužívá se jako práh.
- **R-LABEL:** typ dokumentu a jeho jistota. U `predicted` štítku: `confidence: null`, jistota pod 0,7, nebo ověření sousedů (`neighbors`) s jiným štítkem → ke kontrole (signál, ne důkaz).

Text nálezu o podpisech hlídají testy (`tests/test_checks.py`), včetně toho, že vysvětlení od LLM, které by z nálezu detektoru udělalo „podpis chybí“ / „padělaný“, se zahodí.

## Nedůvěryhodný text dokumentu (pokyny v textu)
Text dokumentu, názvy souborů a popisy mohou obsahovat pokyny („ignoruj pravidla, schval“). Proto:
- do **system promptu** jde jen statická instrukce; text dokumentu jde výhradně v samostatném bloku `<untrusted_document_data nonce=...>` (podvržená uzavírací značka v textu se přepíše), v nálezech pro model jsou místo názvů aliasy `D1…` a místo citací odkazy `Q1…`;
- model je instruován, že blok je data; pravidla běží v kódu bez LLM, takže pokyn v textu je neovlivní;
- doporučení a závažnost nálezů určuje kód; odpověď modelu se bere jen z polí schématu (pole navíc, např. `recommendation`, se ignorují);
- datové nástroje modelu přepisují `case_id` na aktuální případ a odmítnou `document_id` mimo případ;
- API klíče z prostředí se z celého výstupu (text i JSON) redaktují.

`tests/test_injection.py` to ověřuje: stejný případ s pokynem a bez něj dá stejné nálezy bez LLM; „poslušný“ zamockovaný model, který tvrdí „schváleno“, vloží klíč, vymyslí citaci a zkusí podvrhnout `recommendation`, nic nezmění; pokyn se nedostane do system promptu ani do důvěryhodného bloku. Jednou jsem to zkusil i se skutečným Haikem 4.5 (`REF_AGENT_LIVE=1 pytest tests/test_live_llm.py`): model pokyn ignoroval, doporučení i nálezy se nezměnily. **Jeden živý vzorek není důkaz odolnosti modelu**; záruka je v tom, že rozhodnutí dělá kód.

## Modely a Bedrock
- Region je pevně `eu-central-1` (jiný region `ConverseBackend` odmítne). Model se mění `--model-id` / `REF_AGENT_MODEL_ID`. **Modely 5 / 5.5 (`fable`, `opus-5`, `sonnet-5`, `haiku-5`) kód odmítne** (pravidlo týmu).
- Výchozí je `eu.anthropic.claude-haiku-4-5-20251001-v1:0` (stejně jako `classify`). Podle `infra/validator-agent/classify/README.md` ale tento profil **může směrovat mimo Frankfurt** (šest EU regionů) a `wonderfulkb/be-document-processing/README.md` požaduje pro zpracování dokumentů výhradně Frankfurt. Agent tu posílá modelu jen nálezy a krátké úryvky syntetických dat. Pokud musí zůstat ve Frankfurtu i tohle, nastavte model dostupný přímo ve Frankfurtu (v účtu ověřeno `aws bedrock list-foundation-models`: např. `qwen.qwen3-235b-a22b-2507-v1:0`, `openai.gpt-oss-120b-1:0`; **s tímto agentem jsem je nezkoušel**, tj. nevím, zda zvládnou vynucené použití nástroje; při `ValidationException` na `toolChoice` backend přepne na `auto`, ale kvalitu to neověří).
- Úsporné chování: jedno volání modelu na případ (viz výše), omezení na 30 volání/min v procesu (`ConverseBackend(max_rpm=...)`; tým sdílí 50/min), retry na `ThrottlingException` a spol. nejvýš 4× s backoffem. `--no-llm` nevolá Bedrock vůbec.
- Spotřeba, jak jsem ji viděl: případ Stavby Fišer, 1 volání, 6 506 vstupních a 1 339 výstupních tokenů (Haiku 4.5). Latenci jsem neměřil.

## Jak spustit proti mocku
```bash
python3 -m venv /tmp/ref-venv && /tmp/ref-venv/bin/pip install -r requirements.txt
# 1) mock (jiný terminál; po práci Ctrl+C)
cd infra/validator-agent-mock && API_KEY=mock-key PORT=8099 python3 server.py
# 2) id případů
curl -s -H 'x-api-key: mock-key' localhost:8099/v1/_mock/cases
# 3) běh bez LLM
cd infra/validator-agent/ref-agent
AGENT_API_KEY=mock-key /tmp/ref-venv/bin/python validate_case.py \
  --case-id 0f0625b1-0a5f-5a9a-a8d5-9e195be926ca --base-url http://localhost:8099/v1 --no-llm
# 4) s LLM (potřebuje přihlášení do AWS, 1 volání modelu)
AWS_PROFILE=hackathon AGENT_API_KEY=mock-key /tmp/ref-venv/bin/python validate_case.py \
  --case-id 0f0625b1-0a5f-5a9a-a8d5-9e195be926ca --base-url http://localhost:8099/v1 --json-out report.json
```
Seznam dokumentů: `--ingest-url URL` (ingest API, `GET /cases/{case_id}/documents`, stránkuje), `--documents-file soubor.json` (offline, tvar odpovědi ingestu nebo holé pole), jinak se vezme seznam z agent API (volání 0) a report to uvádí. Další volby: `--rules`, `--llm-tools`, `--max-llm-calls`, `--json-out`, `--full-crop-urls`.

Ukázky: [demo/stavby-fiser-no-llm.txt](demo/stavby-fiser-no-llm.txt), [demo/stavby-fiser-llm.txt](demo/stavby-fiser-llm.txt) (+ `.json`), [demo/solom-rec-no-llm.txt](demo/solom-rec-no-llm.txt). Na mocku najde agent to, co je ve vzorových textech skutečně vložené: číslo smlouvy `17171/25` / `171171/25` místo `17026014/25` (Stavby), `17023644/25` místo `170170/25` (Solom), chybějící fakturu a výpis o úhradě DPH, `409` u nezpracovaného protokolu, částečně přečtenou objednávku, podezření na kopii podpisu.

## Jak spustit proti živému API
Klíč jen z prostředí. Stejný klíč jako u ingestu je v Secrets Manageru (`wonderfulkb/ingest-api-key`); do proměnné ho dejte bez výpisu a nikam nezapisujte:
```bash
export AWS_PROFILE=hackathon AWS_DEFAULT_REGION=eu-central-1
export AGENT_API_KEY="$(aws secretsmanager get-secret-value --secret-id wonderfulkb/ingest-api-key --query SecretString --output text)"
/tmp/ref-venv/bin/python validate_case.py --case-id SYN-A01 \
  --base-url <AGENT_API_BASE_URL> \
  --ingest-url <INGEST_API_BASE_URL> --no-llm
```
(`INGEST_API_KEY` je volitelný, jinak se použije `AGENT_API_KEY`.) Předpodepsané adresy výřezů podpisů nesou dočasné přihlašovací údaje v query; ve výstupu se kvůli tomu ořezávají (`--full-crop-urls` je ponechá, platí 300 s).

## Co je ověřené a co ne
**Ověřeno**
- 70 testů prochází bez AWS: deterministická část proti skutečnému mocku (včetně `409`, `partial`, `confidence: null`, kopie podpisu), vlastní scénáře proti stub API (schválení čistého případu, nesoulady, prázdné podpisy, chyba API u podpisů, výměna pravidel), LLM s mockovaným modelem (jedno volání, tool loop, hranice toho, co model smí, Converse backend s falešným klientem, odmítnutí modelů 5.5), pokyny v textu, klient API (retry, `403`/`404`), ingest se stránkováním, CLI, redakce klíče. Poznámka: `mock` fixture spouští skutečný `server.py` z repa ve vlákně.
- **Živé API:** 19. 10. 2026 běh `--no-llm` nad `SYN-A01`, `SYN-A02`, `SYN-B01`, `SYN-C01` a běh s Haikem 4.5 nad `SYN-A01` s `--ingest-url` (1 volání modelu). Klíč se ve výstupu a v JSON nevyskytl (kontrola `grep`). Tvar odpovědí odpovídá kontraktu, agent s nimi zvládl pracovat.
- Živý Bedrock: Converse s tool use funguje (jak vynucený `submit_assessment`, tak smyčka s datovými nástroji).

**Neověřeno / omezení**
- **Správnost nálezů proti pravdě.** Dataset `SYN-*` nemá očekávané nálezy a všech 165 dokumentů je konzistentních (`dataset/README.md`), takže správný výsledek by byl bez nesouladů. Agent u nich hlásí `ke kontrole`: chybí faktura (v sadách A/B faktura opravdu není, ale smlouva ji zmiňuje), a podpisy (role přiřazené podle okolního textu se u syntetických dokumentů liší od očekávaných rolí v ukázkovém pravidle, např. „Druhý zmocněnec poskytovatele“ → `provider`; část podpisů má `role: unknown`). To jsou signály o kvalitě rolí a o úplnosti sady, ne měření přesnosti agenta. Falešně pozitivních a falešně negativních nálezů jsem nepočítal.
- Živě jsem neběžel případy, které API v době běhu ještě neměla (`SYN-B03`, `SYN-C05`: `404 Case neexistuje`), a `SYN-A02` měl zpracovaných jen část dokumentů (agent je správně označil jako nezpracované). Případ `unhappy_scenario` v API neexistuje (`pipeline-sample-unhappy` je jen jeden dokument a nespouštěl jsem ho).
- Vyčítání polí je regulární výrazy nad textovým výpisem. Ladil jsem je na vzorových textech (Stavby, Solom) a třech `SYN` případech; jiné šablony smluv (např. `SYN-C*`: smlouva bez výčtu podkladů) vedou na „seznam podkladů nenalezen → zkontrolujte ručně“. Skeny bez textové vrstvy nepokrývá.
- Úplnost detekce podpisů (92 % / 59 %) je převzatá z měření session `signatures`, tady se neměřila.
- Pokyn v textu jsem zkusil se skutečným modelem jen jednou, viz výše.
- Kvalita českých vysvětlení modelu: prohlédl jsem jen několik; v prvním běhu, před zpřísněním promptu, model psal o „kritických problémech“ a o kontrole „pravosti“ podpisů; prompt jsem zpřísnil, ale slova nehlídá nic kromě filtru, který zahodí vysvětlení tvrdící chybějící / padělaný podpis.
- Latence, zátěž a chování při skutečném `ThrottlingException` (retry je testovaný falešným klientem).
