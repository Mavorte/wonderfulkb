# privacy/measure: úplnost zamaskování a migrace do nových klíčů

Krok 1 (měření úplnosti zamaskování, bez zásahu do AWS dat) a krok 4 (migrace stávajících dat do nových klíčů, bez mazání) z [be-validator-agent/docs/validator-agent-privacy.md](../../../../be-validator-agent/docs/validator-agent-privacy.md), část 8. **Výsledky a doporučení: [report.md](report.md).** Postup zálohy před případným smazáním: část 8a téhož dokumentu.

| Soubor | K čemu |
|---|---|
| `fetch.py` | stáhne PDF (165 dokumentů datasetu, 16 původních) a stávající `signatures.json` do NOVÉ PRÁZDNÉ složky; jen čtení z S3 |
| `measure.py` | redakce všech PDF lokálně + `verify_redacted` + pravdivé podpisy (pokrytí boxu i pixelová kontrola) + kolaterální změna; scénáře `zones`, `findings`, `local`, `pipeline`, `pipeline_vec`; varianty zón `v1`, `v2`, `v3` |
| `zones.py` | konzervativnější zóny `v2` (podle role a funkce, i na skenech přes OCR) a `v3` (užší zóny na skenech) |
| `verify_tolerant.py` | `verify_redacted` bez falešných poplachů na okrajích slov (viz report) |
| `tables.py` | z `results_*.json` udělá tabulky (Wilsonovy 95% intervaly), skupiny A a B nikdy sloučené |
| `inspect_leftovers.py` | uloží vedle sebe originál a zamaskovanou kopii u podpisů, kterým zbyl inkoust (ruční prohlídka) |
| `migrate.py` | krok 4: výchozí `--dry-run`; `--apply` zapisuje jen nové klíče a pole podle zadání (viz docstring) |
| `backup_readable.sh` | záloha čitelných dat před smazáním; `--plan` je jen čtení; **nespuštěno** |

## Spuštění měření

```bash
# prostředí: jen existující venv (PyMuPDF, numpy, Pillow, boto3, cryptography), nic nového se neinstaluje
PY=../../pipeline/.venv/bin/python
eval "$(AWS_PROFILE=hackathon aws configure export-credentials --profile hackathon --format env)"
$PY -I fetch.py /cesta/k/nove/prazdne/slozce          # PDF jsou nedůvěryhodná data: nová prázdná složka, mimo repozitář
$PY -I measure.py DATA OUT --scenario pipeline --zones v2 --cache CACHE --render-b --keep-pdf --shard 0/4   # a 1/4 .. 3/4
$PY -I tables.py 'OUT/results_pipeline_v2.shard0.json' ... --list
```

Skripty se spouštějí s `-I` (stažená data nikdy neleží ve složce skriptu). Scénář `pipeline` volá Textract (`AnalyzeDocument`, jen funkce SIGNATURES, jen pro skeny a rukopis; odpovědi se cachují podle SHA-256 stránky); digitální PDF dostanou lokální zálohy bez služby (`--textract-all` volá Textract i pro ně).

## Migrace (krok 4)

```bash
$PY -I migrate.py --only SYN-A01/34fcd896-107a-583f-a406-6a8100cf8150 --cache CACHE   # dry-run jednoho dokumentu
$PY -I migrate.py --all --cache CACHE --report plan.json                                # dry-run všeho
$PY -I migrate.py --only CASE/DOC --apply ...                                           # zápis jednoho dokumentu
```

Zapisuje jen: `cases/<case>/redacted/<doc>.pdf`, `analysis/<doc>/signatures/<sig>.png.enc` a `.preview.png`, tři pole v `signatures.json` (`crop_s3_key`, `crop_encrypted`, `preview_s3_key`; zápis podmíněný na ETag, `overwrite=True` je povinné), existující vektory `#p<n>` v `wonderfulkb-image` (přepočet ze zamaskovaných stránek) a atribut `original_sha256` v řádku `wonderfulkb-uw-document-analysis`. Nové objekty se zapisují s `If-None-Match: *`, existující se nikdy nepřepíšou. Třída `Guard` nemá žádnou operaci mazání. Stav migrace (zastavena po jednom testovacím dokumentu, na pokyn uživatele): [report.md](report.md), část 8.

## Co je ověřeno a co ne

Ověřeno (měřeno, viz report):
- úplnost zamaskování na 165 syntetických dokumentech skupiny A (323 pravdivých podpisů z anotací) a na 16 původních PDF skupiny B (15 stran se 37 podpisy, ruční prohlídka všech těchto stran);
- `verify_redacted` na všech 181 PDF pro každý zkoušený scénář; kolaterální změna (plocha oblastí, změna pixelů mimo oblasti, velikost souboru);
- `migrate.py --dry-run` na 91 dokumentech z asi 204 (přerušeno na pokyn) a skutečný zápis s round-trip na JEDNOM dokumentu (SYN-A01 / 34fcd896…); ostatní dokumenty se nemigrovaly.

Neověřeno:
- **zóny `v2`/`v3` jsou navržené na datech, na kterých se měří** (rozložení podpisového bloku syntetických dokumentů); výsledek 100 % na skupině A proto nejde brát jako odhad pro cizí dokumenty. Skupina B (jiné rozložení, rukopis) je malá (37 podpisů, jeden posuzovatel, bez druhé kontroly);
- pravdivý box skupiny A pro skeny je z anotace v bodech PDF; u skenů s posunem nebo natočením nemusí box sedět přesně. Pixelová kontrola proto počítá inkoust v boxu, ne přesnou polohu podpisu, a zbytky jsem u skupiny A prohlížel očima na výřezech;
- strany bez podpisů v anotaci (a podpisy mimo anotaci) se neprohlížely;
- nic mimo AWS stack (jiné čtenáře `original/…`, ingest) migrace nemění; přepnutí `s3_key` na `redacted/…` není součástí;
- čitelnost náhledů pro lidské oko (jen test na syntetických datech v `tests/`).
