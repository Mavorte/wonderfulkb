# Plan 2026-10-19: Case & Client — evidence-only verification after waiver

tdd: skip

## Analysis
- Posuzovat funkční požadavky `plans/tasks/2026-10-19_case-client-lambda-mock.md`, původní plán `plans/2026-10-19_task-8e06a0bb-7a44-449d-90f5-b7f22b9fc99a_case-client-jedna-lambda-s-explicitn-mi-mock-daty-offline.md` a nezměněné OpenAPI 1.3.0-final; historické TDD pokyny nahrazuje waiver Michala z 2026-10-19 14:29 Europe/Prague (message1561717880481910827).
- Zachovat existující čtyři soubory `be-case-client/src/`, dvě testovací sady, čtyři eventy, README a SAM šablonu; při převzetí zachytit baseline obsahu i untracked souborů, protože komponenta je nyní v `git status --short` převážně untracked a samotný `git diff` ji nepokrývá.
- Použít z proposalu `docs/proposals/proposal-20261019-114433-08800d_case-client-lambda-vyvoj-nezavisly-na-externi-databazi.md` pouze decisions/lambda-mock; nepřebírat novější DB/deploy rozsah. Dodržet dodané root AGENTS.md a pracovat na feature větvi; PlantUML diagramy nebyly nalezeny.
- Aplikovat learnings `architecture/decisions-case-client-mock-fixture-pagination.md`, `architecture/2026-10-19_in-memory-lambda-mocks-provide-only-execution-environment-lo.md`, oba `runtime-errors/*cursor*` a `tooling/2026-10-19_static-sam-checks-cannot-establish-deployed-gateway-behavior.md`: rozlišit lokální idempotenci, přenositelnost fixture tokenů, odmítnutí hlubokého JSON a statickou konfiguraci od runtime gateway. Recall použil backend `local`, collection `wonderfulkb-learnings`, diagnostic `Collection not found: wonderfulkb-learnings`.

## Approach
- Provést evidence-only kontrolu aktuálních bajtů; nepovažovat historické výsledky za aktuální běh a nevykládat waiver jako potvrzení validity historického proofu.
- Zachovat ancestry a veškeré původní checkpoint/evidence/red-green-proof/acceptance artefakty; nezískávat ani nevyrábět RED, stubs či retrospektivní proof.
- Použít `validate-implementation` při závěrečné kontrole rozsahu a `write-review-report` na konci navazující review fáze; nezávislou acceptance předat callerovi a `acceptance` použít pouze s jeho run manifestem. Tuto plánovací fázi neoznačovat za provedenou acceptance.

## Implementation
1. Zachytit počáteční `git status --short` a obsahové hashe komponenty, OpenAPI a historických artefaktů do nového `plans/checkpoints/task-ba84dff1-cb7e-41c4-b12c-01aefd9591db.evidence.md`; při závěru porovnat baseline včetně untracked souborů. Neměnit task storage, registry, konfiguraci ani historii.
2. Do stejného evidence souboru vytvořit stručnou matici požadavek → konkrétní soubor/test → aktuální výsledek nebo mezera. Zkontrolovat skutečný handler + adaptér, nikoli pouze názvy testů:
   - Čtyři REST routy, veřejné JSON tvary/allowlist, marker mock, konfiguraci fail-closed, sanitizované provozní 500 a absenci SDK/credentials/sítě či zápisu do úložiště.
   - AND filtry a normalizaci celých právních forem, query-bound tokeny včetně cizího/neplatného/hluboce zanořeného JSON, validaci ID/UUID/JSON/base64/metadata 16KiB, řazení a stránkování cases i chybějícího/prázdného klienta.
   - 201→200 se zachováním metadat/času v jedné repository, precedence existujícího ID před stavem klienta, 409 jiné vlastnictví/inactive/blocked, 404 chybějící klient, atomický souběh, hluboké kopie a reset nové repository.
   - Syntetické fixtures a zabalené eventy; jedinou Python3.13 funkci 256MB/10s s `CodeUri: src/`, REST stage v1/čtyři key-protected routy, key/usage-plan/stage vazbu, JSON 403/429, krátkou retenci, pouze scoped log IAM, project tagy a nesekretní outputs bez DB/S3/VPC resources/práv.
   - README: přesné offline příkazy bez globálního PYTHONPATH/SAM/Docker, explicitní ephemeral omezení, přímé CodeUri balení a oddělený host runbook; žádný slib persistence ani spuštění jeho cloudových příkazů.
3. Spustit brány v sekci Testing; zaznamenat přesné příkazy, exit kódy, počty testů a named blockers. Neinstalovat chybějící nástroje ani neměnit konfiguraci kvůli úspěchu brány.
4. Při skutečném defektu nejprve uvést požadavek, soubor/řádek, vstup a expected/actual; povolit pouze minimální opravu v `be-case-client/**` a cílenou regresi bez povinného RED. Zachovat sílu assertions a znovu provést dotčené testy i závěrečné brány. Bez doloženého defektu produkční kód neměnit; při blockeru reportovat přesnou mezeru místo neodůvodněné opravy.
5. Předat aktuální evidence a diff k nezávislé acceptance se stejným waiverem; zaznamenat její skutečný výsledek nebo stav pending. Závěrečná poznámka propojí tento kanonický plán, evidence a review report, uvede změněné soubory, výsledky/blockery, lokální persistenci a neprovedený deploy/smoke.
6. Jako poslední pracovní krok navazujícího ověření použít `save-learning` a uložit alespoň jeden konkrétní poznatek; historické soubory nepřepisovat.

## Testing
Spustit z kořene repozitáře; uchovat aktuální výstupy odděleně od historických důkazů:

```sh
python3 --version
python3 -m unittest discover -s be-case-client/tests -p 'test_*.py' -v
python3 -m compileall -q be-case-client/src
npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build
```

- Ověřit pokrytí existujícími `test_case_client_lambda.py` a `test_case_client_template.py`, včetně `test_pagination_query_binding_and_cross_repository` s hlubokým tokenem; nepředepisovat historický počet jako očekávaný výsledek aktuálního běhu.
- Zjistit lokální dostupnost SAM CLI; pokud je dostupné, spustit čistě lokálně `sam validate --lint --template-file be-case-client/template.yaml` bez AWS API/credentials lookup. Chybějící `AWS SAM CLI (sam)`, lint dependency či jiný blocker uvést s přesným neprovedeným/selhavším příkazem; statické unittest kontroly nenahrazují SAM validaci.
- Zachovat registrovanou frontendovou bránu přesně výše; Vitest a TypeScript/Vite build nesmějí být nahrazeny backendovým subsetem. Kanonický registry snapshot použít bez čtení či přepisování externího registry.
- Neprovádět AWS deploy/cloud smoke, live zprávy/provider operace ani service/config/credential změny; key ochranu popsat pouze jako staticky zkontrolovanou, pokud není nezávislý runtime důkaz v povoleném scope.

## TDD
N/A — explicitly waived by Michal 2026-10-19; ordinary tests remain required.

## Files
| Cesta | Povolená akce |
|---|---|
| Tento kanonický plán | Uchovat waiver a postup; odkaz předat callerovi pro stav, task soubor neupravovat. |
| `plans/checkpoints/task-ba84dff1-cb7e-41c4-b12c-01aefd9591db.evidence.md` | Nová aktuální baseline, matice požadavků a výstupy bran v navazující fázi. |
| Review report v cestě určené `write-review-report` | Nový nezávislý review výsledek, nikoli přepis původní acceptance. |
| `be-case-client/**` | Číst a ověřovat; editovat pouze při doloženém defektu včetně minimální regrese; OpenAPI zachovat. |
| `learnings/**` | Uložit nový relevantní poznatek přes `save-learning`. |

## Progress
- [x] Získat kanonickou cestu a přečíst původní brief/plán, strukturu komponenty, testy a relevantní learnings.
- [x] Naplánovat aktuální evidence, funkční kontroly, brány a nezávislou acceptance s explicitním TDD waiverem.
- [ ] V navazující fázi provést lokální ověření, uložit evidence a dokončit nezávislou acceptance; během plánování se testy ani implementace neprovádějí.
