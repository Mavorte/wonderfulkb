# Plan 2026-10-19: Case & Client — doplnění historické TDD provenance

## Analysis
- Použít původní plán `plans/2026-10-19_task-8e06a0bb-7a44-449d-90f5-b7f22b9fc99a_case-client-jedna-lambda-s-explicitn-mi-mock-daty-offline.md`, zejména TDD ř. 33–36, jako kontrakt: import diagnostic nestačí; doložit assertion nad importovatelnými stuby před implementací.
- Zachovat `plans/checkpoints/task-8e06a0bb-7a44-449d-90f5-b7f22b9fc99a.red-green-proof.md`: RED 12:16:34 UTC má 13 ModuleNotFoundError; GREEN 12:20:34 UTC má 13 úspěšných testů. Nevydávat tento RED za behaviorální.
- Prověřit kandidáta z původního `.checkpoint.md`, ř. 13: run `75100192d4794793a734d11161f010c9`, označený `rejected_false_green`, údajně se skutečnými assertion failures nad stuby; checkpoint sám není náhradou raw stderr.
- Zohlednit mezery původního `.evidence.md`: session `swift-wave-0887`, `command_lines_truncated`, `outcome_unavailable`; chybějící argv ani výsledek nedovozovat ze souhrnu.
- Zachovat existující soubory: handler má reálný adaptér a fail-closed konfiguraci, testy importují oba moduly v setUp. `git status --short` ukazuje implementaci i důkazy jako untracked; `git log` končí `65a779b`, nikoli commitem Lambda implementace. Nepovažovat chybějící git historii za chybějící práci.
- Použít recall pravidla z `learnings/tooling/rules-planning-retry-canonical-header.md` a `learnings/runtime-errors/rules-case-client-cursor-json-depth.md`: dodržet kanonický formát a nezaměnit pozdější regresní 500/400 RED za požadovaný stub RED. Recall backend `local`, collection `wonderfulkb-learnings`, diagnostic `Collection not found: wonderfulkb-learnings`.

## Approach
- Doplnit samostatný provenance addendum pod follow-up taskem s odkazy na nezměněné rodičovské artefakty; nepřepisovat immutable proof ani znovu nevytvářet stubs.
- Použít `skill:task-evidence` pro dohledání lineage, `skill:tdd` pro podporovaný způsob evidence/historického RED a fresh GREEN, `skill:save-learning` jako poslední dokončovací krok.

## Implementation
1. Před zápisem ověřit aktuální pracovní strom a zaznamenat SHA-256 existujících `be-case-client/**` a původních důkazů; na konci porovnat obsah. Zachovat i untracked soubory.
2. Přes `skill:task-evidence` spustit `python3 /Users/michal/.config/opencode/skills/task-evidence/scripts/fetch-evidence.py --task task-ba84dff1-cb7e-41c4-b12c-01aefd9591db --project-dir .`; přečíst vygenerovaný artefakt a přes dostupné session/run logy dohledat výše uvedený run. Existující rodičovský evidence soubor nepřegenerovat přes jeho originál.
3. U kandidáta doložit úplné argv/cwd, původní timestamp, exit code, nezkrácené stdout/stderr a zdrojový run/session identifikátor; doložit úspěšný import/setUp, konkrétní assertion (expected/actual, test a řádek) a pořadí stubs → RED → implementace → rodičovský GREEN. Označení helperu „green“ není samo o sobě důvod odmítnout skutečný neúspěšný běh, ale `rejected_false_green` výslovně zachovat.
4. Ověřit shodu historického focused argv s rodičovským proof metadatem; test-file fingerprint/revizi převzít pouze ze skutečně dostupných historických podkladů. Oddělit historických 13 testů od pozdějšího rozšíření na 14; žádné výsledky nepřipsat zpětně.
5. Pokud autentický stub RED a jeho pořadí nelze doložit, zapsat přesný blocker a dostupné mezery; finding-001 ponechat nevyřešený a předat callerovi k rozhodnutí. Nevyrábět RED pomocí revertu, mutation, nových stubů či úprav testu a netvrdit, že fresh GREEN opravuje chybějící historii.
6. Zachytit fresh focused GREEN a regresní brány níže s novým task ID. Po načtení `skill:tdd` použít podporovaný historický odkaz; pokud helper historický import neumí, uložit transparentní addendum a raw výstupy bez ručního falšování jeho metadat. Případnou nekompatibilitu kanonického proof formátu výslovně předat callerovi.
7. V addendu propojit import diagnostic → autentický behaviorální stub RED → původní GREEN → fresh GREEN; uvést přesné příkazy, výsledky, mezery a odkaz na tento plán. Checkpoint označit complete pouze při doložené provenance a úspěšných branách.
8. Jen při nově doloženém skutečném implementačním defektu zdokumentovat reprodukci a eskalovat minimální fix s testem dle `skill:tdd`; samotná mezera v evidenci neopravňuje měnit produkční kód. Na závěr použít `skill:save-learning` a uložit konkrétní poznatek.

## TDD
- Přeskočit nový RED/GREEN vývojový cyklus: výstupem je evidence existujícího programu, nikoli změna chování. Zachovat plnou povinnost historického behaviorálního RED dle původního plánu; tento follow-up ji neruší.
- Použít existující `be-case-client/tests/test_case_client_lambda.py`, nikoli nový skeleton. Historický i fresh focused příkaz musí mít stejné argv: `python3 -m unittest discover -s be-case-client/tests -p 'test_case_client_lambda.py' -v`.

| Fáze | Požadovaný důkaz |
|---|---|
| Původní import diagnostic | Nezměněný rodičovský proof, 13 setup errors; nesplňuje behaviorální RED |
| Historický stub RED | Raw původní běh s importovatelnými stuby, konkrétním failing assertion a doloženým pořadím před implementací |
| Původní GREEN | Tentýž focused argv, exit 0 v původním proof |
| Fresh GREEN | Tentýž focused argv nad zachovanou implementací, nový timestamp/task ID, exit 0 a úplný výstup |

## Testing
- V navazující realizaci spustit z kořene a uložit command → exit code → skutečný výsledek:
  - `python3 -m unittest discover -s be-case-client/tests -p 'test_case_client_lambda.py' -v`
  - `python3 -m unittest discover -s be-case-client/tests -p 'test_*.py' -v`
  - `npm --prefix apps/backoffice test && npm --prefix apps/backoffice run build` — registrovaná brána, timeout 300 s.
- Ověřit SHA-256 readback zdrojů, testů, fixtures, šablony, OpenAPI a původních proof/checkpoint/evidence souborů; `git diff --check` doplnit kontrolou nových untracked artefaktů, které git diff nezahrne.
- Zkontrolovat existenci všech citovaných artefaktů a přesnost provenance. Absenci historických raw logů nebo úplného argv uvést jako blocker, nikoli PASS. SAM/deploy důkazy nejsou součástí této opravy; předchozí chybějící SAM CLI nezaměňovat za nově provedenou validaci.

## Files
| Cesta | Akce v navazující realizaci |
|---|---|
| `plans/checkpoints/task-ba84dff1-cb7e-41c4-b12c-01aefd9591db.evidence.md` | Lineage výstup helperu; zachovat mezery a přesné příkazy |
| `plans/checkpoints/task-ba84dff1-cb7e-41c4-b12c-01aefd9591db.tdd-provenance.md` | Historické odkazy, ověřený raw stub RED, fresh GREEN výstup a stav finding-001 |
| `plans/checkpoints/task-ba84dff1-cb7e-41c4-b12c-01aefd9591db.checkpoint.md` | Postup, ověřovací výsledky, blocker nebo doložené dokončení, odkaz na tento kanonický plán |
| `learnings/tooling/` | Jeden konkrétní poznatek přes `skill:save-learning` |

## Progress
- [x] Získat kanonickou cestu, přečíst původní plán, proof, checkpoint, evidence, relevantní kód a learnings.
- [x] Připravit evidence-only postup s konkrétním historickým kandidátem a větví pro nedostupnou provenance.
- [ ] V navazující realizaci získat raw historický stub RED, zachytit fresh GREEN a rozhodnout stav finding-001 podle důkazů.
# Case & Client — evidence-only verification plan

tdd: skip

## Analysis
- Read original requirements, original plan and existing implementation; preserve historical evidence and apply the operator waiver dated 2026-10-19.

## Approach
- Plan offline functional verification and the registered project gate; allow production corrections only for an evidenced defect.

## TDD
N/A — explicitly waived by Michal 2026-10-19; ordinary tests remain required.

## Progress
- [x] Resolve dedicated canonical plan path.
- [ ] Inspect repository requirements, implementation and relevant learnings.
- [ ] Finalize concrete verification commands and evidence deliverables.
