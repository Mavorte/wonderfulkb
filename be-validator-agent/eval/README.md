# Evaluace end-to-end (Fáze C)

`evaluate_e2e.py` změří kvalitu celého toku „PDF → zpracování → čtecí API validačního agenta“ na zpracovaných případech
a vypíše report (markdown + JSON). Čte jen přes agent API (seznam + 3 volání), nic nezapisuje do AWS a nic nenasazuje.

| Soubor | Co |
|---|---|
| `evaluate_e2e.py` | hlavní skript: sběr volání, vyhodnocení, výstup |
| `e2e_metrics.py`, `e2e_report.py`, `e2e_transport.py` | metriky (čisté funkce), markdown, zdroje dat (HTTP, lokální handler, mock) |
| `truth.yaml` (+ `truth.json`) | pravda: typ, stránky, podpisy, scénáře, u každé hodnoty zdroj |
| `build_truth.py`, `originals_review.yaml` | generátor pravdy z balíku; ruční kontrola podpisů původních dvou případů |
| `fixture_api.py` | fixturové API (odpovědi z pravdy s chybami) jen pro testy a ukázku; **není měření** |
| `mapping_example.json` | ukázka vstupu |
| `reports/` | ukázkové reporty (mock, fixtura) |
| `tests/` | pytest (bez AWS) |

## Spuštění

Potřebuje Python 3.10+ a stdlib. `truth.yaml` čte PyYAML, bez něj se načte stejný `truth.json`. Testy a `--local-fixtures`
potřebují pytest a moto: použij `infra/validator-agent/pipeline/.venv/bin/python`.

```bash
cd infra/validator-agent/eval

# nasazené API (klíč jen v prostředí, nevypisuje se; mapping výchozí ../dataset/mapping.json)
export AGENT_API_KEY=...            # záloha: API_KEY
python3 evaluate_e2e.py --base-url https://HOST/v1

# lokální handler nad skutečnými AWS (core.handle; klíč se negeneruje ani nečte ze Secrets Manageru)
AWS_PROFILE=hackathon python3 evaluate_e2e.py --local-handler

# mock z infra/validator-agent-mock spuštěný v procesu (bez AWS); mapping se vezme z jeho indexu
python3 evaluate_e2e.py --mock --groups original

# totéž nad kódem API a moto fixturami (bez AWS)
../pipeline/.venv/bin/python evaluate_e2e.py --local-fixtures --groups original

# ukázka celého reportu z vygenerovaných odpovědí (NE měření)
python3 evaluate_e2e.py --fixture
```

Výstup jde do `--out-dir` (výchozí `reports/`) jako `<name>.md` a `<name>.json` a na stdout (`--quiet` ho potlačí).
Další volby: `--neighbors N` (výchozí 3, `similar_to_verified`), `--sample-values K` (u K dokumentů ověří hodnoty vektorů),
`--retries`, `--timeout`, `--workers`, `--sleep`, `--groups`, `--limit-cases`, `--call-all`.
Případ, který v mappingu není (originály zpracované pipeline, např. `pipeline-sample-solom-rec`), se přidá
`--auto-case pipeline-sample-solom-rec=solom-rec`: dokumenty se vezmou ze seznamu API.

Mapping (`../dataset/mapping.json` od v-dataset) se spáruje s pravdou podle **`sha256`** dokumentu (spolehlivé), jinak podle
`source_case` / `truth_case` (např. `SYN-A01`), jinak podle ID případu v `case_id`, a u původních případů podle shody názvů
souborů. Názvy souborů `SYN-A01` až `SYN-A05` jsou shodné, takže bez jedné z prvních možností se případ nepřiřadí a
vypíše se v „Co nelze změřit“. Pole `scenario` v mappingu je volný text; mimo šest scénářů (`happy_path`, `chybi_dokument`,
`spatny_dokument`, `spatne_udaje`, `chybi_podpis`, `nevytezi_se`, nebo čísla 1 až 6) se scénář vezme z pravdy.
Volitelná pole pro upravené varianty dokumentů: u případu `removed_documents: [soubor]`, u dokumentu
`variant: {removed_signatures: [{page, role?}]}`.

## Co se měří

Report má pro každou skupinu zvlášť (`generic`, `original`) tyto sekce. U každého podílu je 95% Wilsonův interval a
varování u malého vzorku (`n < 30`; skupina `original` má 16 dokumentů).

- **Volání 1: dostupnost.** Dokument je dostupný, když je `processing_status` `completed`/`partial` a text není prázdný.
  Dál: shoda `page_count` s pravdou, počet stran v textu (`\f`) = `page_count`, podíl anotovaných hodnot polí (číslo smlouvy,
  výrobní číslo, částky, názvy) nalezených v textu, po vrstvě textu a kvalitě vstupu. To není měření extrakce, jen podmínka,
  aby validační agent z textu vůbec mohl hodnoty přečíst. 409 u nezpracovaného dokumentu není chyba, ale dokument se počítá
  jako nedostupný.
- **Volání 1: štítek a kalibrace.** Přesnost štítku proti pravdě (správný = některý z přijatelných štítků pravdy), záměny,
  podle kvality vstupu a jistoty pravdy. Kalibrace `confidence` jen u `predicted`: průměrná jistota u správných a u špatných,
  rozdíl, koše 0 až 0,5 / 0,5 až 0,7 / 0,7 až 0,9 / 0,9 až 1, ECE a Brier. Dokumenty typů, které taxonomie nezná (`cerpani`,
  `splatky`), se z přesnosti vylučují a uvádí se jejich predikce.
- **Volání 2: vektory.** Existují (text nebo obraz); obrazové vektory jsou přesně strany 1 až `page_count`; textové části
  mají platné rozsahy stran a pokrývají všechny strany s textem; rozměr 1024, modely; `neighbors`: pořadí, rozsah skóre,
  není to sám dokument, štítek v taxonomii, **soused je `verified`** (ověřuje se vůči dokumentům testované sady a indexu
  mocku; sousedé mimo ně jsou „neověřitelní“ a jen se spočítají), a nepřímý ukazatel „štítek nejbližšího souseda = pravda“.
  Hodnoty vektorů (délka = dimenze, konečná čísla, norma kolem 1) se ověří na `--sample-values` dokumentech.
- **Volání 3: podpisy, dvě skupiny odděleně, nikdy jedno číslo.**
  - *Úplnost*: očekávaný podpis nalezen na správné straně, IoU ≥ 0,3 (nebo menší box z ≥ 80 % uvnitř většího při poměru ploch
    do 4×), párování jedna ku jedné. Navíc mírnější „pokrytí“ (≥ 50 % plochy podpisu uvnitř nějakého nalezeného boxu), které
    ukáže sloučené boxy.
  - *Falešné nálezy*: nalezený box, který se nepřekrývá s žádným očekávaným podpisem. Duplicity a sloučené boxy (překrývají
    podpis, ale nespárovaly se) se počítají zvlášť. Podíl falešných nálezů je z nálezů, úplnost z očekávaných podpisů.
  - Dokumenty bez podpisu v pravdě (faktura, výpis, `99_`) s nálezem; dokumenty se správným počtem; role (přesná, s tolerancí
    kupující ≈ dlužník, `unknown`); podle typu dokumentu a kvality; detektory, přítomnost `crop_url`, `phash`, platný `bbox`.
  - `copy_suspicion`: jen informativně, viz níže.
  - **generic**: pravda je s polohou (bbox). **original**: pravda je ruční vizuální kontrola na úrovni strany (počet podpisů na
    straně), proto se porovnává strana a počet, ne poloha, a role se nehodnotí.
- **Latence a chybovost** po voláních: p50, p95, max, stavy, 5xx a síť/časový limit, 4xx (id z mappingu mají existovat),
  409, opakování. Chybovost = 5xx + síť + 4xx mimo 409.
- **Scénáře** (docs/scenare.md): po případech, co lze vidět na úrovni zpracování (chybějící dokument, nedostupný dokument,
  chybějící/přebytečný podpis).
- **Co nelze změřit**: sekce reportu, generuje se z toho, co v pravdě chybí (viz níže).

Metriky jsou kontrakt chování, ne cíle: skript nemá práh „prošlo/neprošlo“ a nevrací chybový kód podle kvality.

## Pravda (`truth.yaml`)

Generuje ji `build_truth.py` z balíku `s3://wonderfulkb-raw-document-storage/cases/synteticke_dokumenty_20_pripadu.zip`
(SHA-256 balíku je v `meta`) a z repa. Každý dokument má `sources` (klíče do `sources:` na začátku souboru).

| Hodnota | Zdroj |
|---|---|
| typ dokumentu (generic) | `kind` v `manifest.json` balíku, převedený na štítek `classify/taxonomy.yaml` (tabulka `label_map`). **Číselný prefix nestačí:** `01` je VOP v sadě A, ale faktura v sadě C |
| typ dokumentu (original) | číselný prefix souboru (`docs/dokumenty-a-skupiny.md`, `docs/vzorove-dokumenty/README.md`) |
| `label_certainty` | `certain` = typ je v taxonomii jmenovitě; `probable` = jen popisem nebo přibližně (předávací protokol z balíku, cenová nabídka, dodací list), přijatelné štítky jsou v `accept`; `unmapped` = taxonomie štítek nemá (potvrzení o čerpání, splátkový kalendář), z přesnosti se vylučuje |
| `page_count`, `quality`, `text_layer` | `manifest.json`, anotace balíku (strany `image_only`), PDF |
| podpisy (generic) | `marks[].signature_bbox` v anotacích balíku (strana, bod PDF, přepočteno na relativní souřadnice podle velikosti strany z PDF), role z českých i anglických názvů převedené na enum OpenAPI. 323 podpisů ve 165 dokumentech. Souřadnice jsem ověřil vykreslením: u 229 z 244 změřených boxů je uvnitř víc inkoustu než ve stejně velkém okně o 150 px vedle, zbylých 15 jsou převážně vybledlé kopie |
| podpisy (original) | `originals_review.yaml`: ruční vizuální kontrola všech 74 stran 16 PDF, počty podpisů po stranách (37 podpisů). Jeden posuzovatel (Claude), bez druhé kontroly, bez pohledu na výstup detektorů; počítá se rukou psaný tah v podpisovém poli včetně tahu přes razítko |
| pole pro kontrolu textu | `fields` v anotacích balíku (až 10 polí na dokument) |
| scénáře | všech 20 případů je `happy_path` bez nálezů: README balíku (korpus je bez vložených chyb, `expected_semantic_consistency: true`); šest scénářů a co z nich jde změřit: `docs/scenare.md` |

Obnova: balík stáhnout do nové prázdné složky, rozbalit, `python -I build_truth.py --bundle <složka> --zip <zip>`
(potřebuje pypdf a PyYAML; skript z balíku jen čte JSON a PDF a nic ze složky nespouští). `truth.json` je identická kopie
pro běh bez PyYAML (test to hlídá).

## Co se neměří (a proč)

- **Podvody a chybové scénáře.** Balík nemá žádný záměrně vadný dokument, žádný scénář s chybou ani seznam očekávaných nálezů.
  Scénáře 2, 5 a 6 jde ověřit, jen když `mapping.json` popíše upravenou variantu; bez toho je verdikt „nelze určit očekávání“.
  Scénáře 3 a 4 (špatný dokument, špatné údaje) hledá validační agent porovnáním dokumentů, tři čtecí volání je nemohou najít.
- **`copy_suspicion`, `similar_signatures`, pravost podpisu.** Pravdivě pozitivní případy neexistují. Tentýž signatář má
  v dokumentech případu shodný základ tahů (`same_signer_in_other_docs` v pravdě), report ukazuje jen, jak se `copy_suspicion`
  rozděluje podle toho, a nehodnotí to jako správné ani špatné.
- **Skupina `original`:** pravda o poloze podpisů a o textu přepisu skenů chybí. Počítá se jen počet podpisů na straně.
- **Typy bez štítku v taxonomii**, pravdivost `description`, kvalita vyhledávání podobných dokumentů (jen nepřímo přes štítek
  souseda a jen tam, kde index obsahuje ověřené dokumenty), kvalita modelu obrazových a podpisových vektorů.
- **Latence** jsou z jednoho klienta bez zátěže a bez řízeného studeného startu.

## Testy

```bash
../pipeline/.venv/bin/python -m pytest          # 56 testů, 1 až 4 minuty podle zátěže stroje, bez AWS
```
Pokrývají metriky (párování podpisů: sloučený box, duplicita, strana, těsný box, velký box), pravdu (počty podle README balíku,
zdroje, štítky v taxonomii, `truth.yaml` = `truth.json`), vyhodnocení proti fixtuře bez chyb (přesně 100 % a 323 podpisů) i
s chybami (musí se zachytit), proti mocku, chování při 500/403/404/časovém limitu, varianty scénářů, přiřazení pravdy podle
sha256 a souborů a to, že se klíč ani `crop_url` nedostanou do reportu.

## Ověřeno a neověřeno

Ověřeno: skript běží proti mocku (`reports/demo-mock.md`), proti kódu API nad moto fixturami a proti fixtuře (`reports/demo-fixture.md`);
`mapping.json` od v-dataset se spáruje se všemi 165 dokumenty podle sha256. **Neověřeno:** běh proti nasazenému API nebo
proti skutečným AWS datům (případy `SYN-*` zatím nemají řádky v `wonderfulkb-uw-document-analysis`; Lambda API není nasazena),
chování `--base-url` mimo mock (HTTP přes `urllib`, jen proti mocku), výkon při velkém počtu souběžných volání.
Čísla v `reports/demo-mock.*` jsou čísla mocku, ne systému: mock dává všechny podpisy na poslední stranu, takže úplnost je nízká.
