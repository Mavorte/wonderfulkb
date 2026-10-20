---
title: "Monitoring: atomicky dokončit sdílené audit event kontrakty a jejich readback"
type: implementation
---
# Atomické dokončení auditních event kontraktů

## Cíl
Jeden source owner dokončí skutečný nedodaný rozsah pěti původních tasků uvedených níže. Nejde o pět dalších paralelních oprav. Historická acceptance infra_inconclusive zůstává. Autoritativní host nálezy: plans/checkpoints/acceptance-host-review-0818-events-domain.md a events-start.md. Pozor: jejich závěr o Decimal decode AttemptStarted je chybný — host přímý syntetický Decimal probe na aktuálním source úspěšně dekódoval attempt_no na int; tuto falešnou diagnózu nepřebírej. Dvě definice AttemptStarted a rozdílné dědičné identity jsou skutečné.

## Co dokončit
- Jediná definice každého event typu, jeden explicitní allowlisted serializer/deserializer; odstranit mrtvé/shadowed duplicity, zachovat veřejné validní API a FileReceived/RunQueued bez změny. Zpětná kompatibilita všech předešlých slices. Žádný broad refactor mimo tento auditní kontrakt.
- Source_validation a extraction Step kontrakty konsolidovat podle přiložených přesných briefů. Aktuálně source/extraction/retry focused dohromady4FAIL/26PASS (roundtrip class identity/equality a neplatné argumenty); naprav skutečnou roundtrip sémantiku, stage/scope/no-content allowlist a Decimal pro číselná pole.
- PageCompleted/PageFailed chybí: doplnit přesné page start/outcome eventy a dispatch; nynější full suite padá při collection test_monitor_page_outcome_events.py. Test-first bez environment pseudoRED. Nevydávej generic Step za page outcome.
- RetryEnqueued/AttemptFinished/RunFinished už existují, ale test je úzký; ověř outcome/attempt_no/identity/order/dedup/terminal-only a kompatibilitu s ostatními typy, safe whitelist, nikdy nevyvozuj definitivní business stav. Nic neprodukuj do worker/queue.
- Pracovní vlastnictví: be-document-processing/src/document_processing/audit/audit_events.py, audit_storage.py, audit_queries.py, jen nezbytný existující audit_listener.py kompatibilní seam; odpovídající test_monitor_{run_queued,attempt_started,source_validation_events,page_outcome_events,extraction_events,retry_terminal_events,audit_storage}.py. Ponech public scalar/NoOp/fail-open isolation; žádný router, pure mapper/reducer, nové eventy z navazujících cache/signature/publication slices nebo producer integrace.

## Ověření, evidence a hranice
Použij projektový `be-document-processing/.venv/bin/python` z kořene repo; pytest zde načítá src přes conftest, pro přímé syntetické probe nastav explicitně `PYTHONPATH=be-document-processing/src`. Nepoužívej systémový python/python3 ani fallback, který způsobil původní nesémantický RED. Ověř závislosti před capture. Pracuj pod NOVÝM vlastním task ID, vlastní plans/checkpoints/<task-id>.red-green-proof.md; staré failed proof/history se nesmí přepisovat, mazat nebo vydávat za green. Genuine RED je požadovaná chybějící vlastnost, ne dependency/collection/environment chyba; stejná argv pro RED/GREEN. Načti skill:tdd a použij skutečně podporované rozhraní, ne čtení zakázaných helper internals nebo obcházení oprávnění. Capability denial je konkrétní blocker.
Spusť jednotlivé focused testy, celou příslušnou audit matici i plné `be-document-processing/.venv/bin/python -m pytest -q be-document-processing/tests`, pak registrované `npm --prefix apps/backoffice test` a `npm --prefix apps/backoffice run build`. Nevyřazuj failing tests ani nesnižuj assertions, nevytvářej collection ignores; odliš unrelated blocker od vlastního výsledku. Testy kvality kontraktu nesmí slepě vyžadovat ValueError tam, kde Python odmítá chybějící/nepovolený argument TypeError; oprav očekávání pouze proti explicitní sémantice neplatného vstupu, ne pro zakrytí skutečné validace.
Pouze wonderfulkb a níže vymezené source/tests plus vlastní task plan/proof/learning. Žádná instrukční/config/platform/task lifecycle změna, nový runtime/dependency/framework ani přístup do jiných repo. Exact module names domain-qualified; žádné utils.py/common.py/state.py/runs.py. No live provider/queue/replay/inference/business writes. Jen HTTP slice níže zachovává své specifické standing test-deploy+live povolení a povinnosti; pure domain slices nic nenasazují. Zachovej ostatní rozpracované source a historické artefakty.

## Přesný původní funkční scope task-e1e34fde-82b5-43aa-a744-aef7b5858293
# Monitoring MVP: AttemptStarted v event deníku

## Goal
Auditní rozhraní uloží skutečně předané zahájení pokusu, bez vlastního vytváření execution identity.
## Files/functions
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`; nový `be-document-processing/tests/test_monitor_attempt_started.py`. Reference `plans/monitoring/live-trigger-evidence-20261019.md` a `mvp-reference-20261019.md`.
## Change
Přidat AttemptStarted: společná obálka + run_id a povinný skutečný kladný attempt_no. Stabilní event_id předá producer; store zachová existující conditional idempotenci a document Query. Bez inference z ApproximateReceiveCount, počtu audit eventů nebo mutable analysis.updated_at. Událost sémanticky označuje úspěšný owned claim/inkrement; tato změna pouze přijímá doložené hodnoty, claim sama neprovádí. Známý live claim dnes žádný counter neinkrementuje; tento kontrakt netvrdí opak.
## Boundaries
Pouze wonderfulkb. Žádný hook do starého Pipeline.process vydávaný za deployed worker, queue/lease/retry/fencing/business změny, counter allocator ani nový timestamp. Žádné terminal/retry události nebo deployment. Neemitovat ani synteticky nevyrábět producer událost pro živý worker bez doloženého kontraktu.
## Verification
Focused pytest/fake: roundtrip FileReceived+RunQueued+AttemptStarted, duplicate nezvýší počet, missing run/invalid attempt odmítnut bez mutation, druhý run/pokus oddělen. Zachovat registrované gates. Implement the TDD cycle using skill:tdd.


## Přesný původní funkční scope task-d2e34593-3eca-44a0-954d-c470eaa95321
# Monitoring MVP: události jednoho ověření vstupu

## Goal
Interní audit přijme a uloží skutečně předané zahájení a výsledek jednoho `source_validation` kroku. Jde o malou event/store část slice 4, ne tvrzení o připojeném živém workeru.

## Files/functions
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`, případně stávající auditní listener pro fail-open předání; nový focused `be-document-processing/tests/test_monitor_source_validation_events.py`. Autorita: proposal `proposal-20261019-150954-c8891f`, sections `data-model`, `instrumentation`, `slice-source-validation`; MVP reference `plans/monitoring/mvp-reference-20261019.md` a source-only poznatky `plans/monitoring/next-slices-source-seams-20261019.md`.

## Change / exact contract
- Přidat pouze `StepStarted`, `StepFinished`, `StepFailed` pro `stage=source_validation`, společnou obálku + povinné předané `run_id`, kladný `attempt_no`. Je to jeden krok config/verze/hash/open, ne událost na každou kontrolu. Identita logického kroku je v tomto slice `(case_id, document_id, run_id, attempt_no, stage)`; eventy mají vlastní stabilní producer-supplied `event_id`. Audit žádnou execution identitu, attempt ani timestamp akce nevytváří.
- Malý typovaný allowlist: `duration_ms` pouze na terminálním eventu a jen je-li skutečně monotónně změřeno (nezáporné finite číslo, jinak neznámé/null); `error_code` jen na StepFailed jako bezpečný technický kód. Referenční kódy checked-in workeru jsou PIPELINE_CONFIG_CHANGED a SOURCE_HASH_MISMATCH; ne raw výjimka/volný popis, S3 cesta, config, hash či obsah. Pro nezmapovanou chybu bezpečný obecný kód, ne serializace výjimky. Žádný `page_number` u tohoto kroku. Nepřidávat obecné details/metadata dump.
- Nevyžadovat přítomnost RunQueued, AttemptStarted ani StepStarted v uložené historii jako podmínku přijetí pozdějšího doloženého výsledku. Ztráta auditu je povolená; terminal-only fragment zůstává čitelný, nevyrábět chybějící event. Persisted idempotence dle event_id, dokumentová partition, occurred_at jako jediný uložený event timestamp a bounded Query zůstávají.
- Chyba validace/tvorby/zápisu při použití auditní business-facing hranice je fail-open; přímý kontraktový validator smí odmítnout malformed event bez mutation. Nespoléhat na catch ve business kódu.

## Boundaries
Pouze wonderfulkb. Žádný producer hook, execution allocator, změna business schématu, lease/retry/queue, runtime, deployment, outbox, backfill ani nový index. Checked-in `be-document-processing/.../pipeline.py:64–73` je sémantická reference, nikoli doložený živý producer; jiný `be-validator-agent/pipeline/run.py` se nesmí potichu zaměnit. Neschválený runtime/outbox návrh v source reportu NENÍ implementační zadání. Jen kontrakt/persistence, ne celý source-validation slice. Nové soubory doménově kvalifikované; žádné events.py/state.py/utils.py.

## Verification
Implement the TDD cycle using skill:tdd. Focused fake/Moto: start→finished a start→failed roundtrip, monotónně předaná duration, duplicate beze změny, terminal-only fragment bez úvodních eventů, missing run/invalid attempt/wrong stage/malformed duration odmítnuty bez zápisu; raw exception/business obsah nesmí projít. NoOp vs failing audit hranice nemění caller výsledek. Zachovat FileReceived/RunQueued/AttemptStarted kompatibilitu a všechny registrované gates. Hermetické testy nejsou live source-validation ani AWS důkaz.


## Přesný původní funkční scope task-164adaf3-99df-429e-86b4-c565e5461be0
# Monitoring MVP: události nové práce a výsledku stránky

## Goal
Existující audit přijme a uloží pouze skutečně předaný začátek nové práce na stránce a její pozorovaný outcome. Malá event/store část slice 5, bez připojování nedoloženého živého workeru.

## Files/functions
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`, malá stávající auditní hranice podle potřeby; focused `be-document-processing/tests/test_monitor_page_outcome_events.py`. Proposal `proposal-20261019-150954-c8891f` sections `slice-page-outcome`, `signals`, `instrumentation`; source report `plans/monitoring/next-slices-source-seams-20261019.md` pouze fakta, nikoli schválení jeho designových návrhů.

## Change / exact contract
- Rozšířit existující StepStarted o `stage=page_transcription`, povinný kladný page_number. Přidat PageCompleted a PageFailed se stejným stage, run_id, kladným attempt_no a page_number; společná obálka a producer-supplied stabilní event_id. Žádné náhradní run UUID, attempt allocator, inference ze SQS receive count nebo z počtu audit eventů.
- Malý typovaný allowlist: na outcome volitelná skutečně monotónně měřená duration_ms (finite >=0); method pouze native/vision a jen při doložené skutečné cestě, model jen když jej skutečná cesta prokazuje, jinak null/vynechat; bezpečný technický error_code na PageFailed. Model config sám není důkaz volání. Bez free-form provider errors či kopie Page objektu.
- Stránkový StepStarted označuje začátek nové práce, ne cache reuse. PageCompleted/PageFailed je jediný terminální outcome tohoto stránkového kroku; nevytvářet další StepFinished/StepFailed pro stejný konec. Při budget/deadline před voláním není placeholder `Page(method=vision)` důkaz skutečného použití metody/modelu, obojí musí zůstat unknown. Cache-hit není nová inference, PageCacheReused patří zvláštní následující sekci a zde se nepřidává.
- Idempotence podle event identity, oddělení run/attempt/page a occurred_at jako jediný uložený čas. Chybějící start/RunQueued/AttemptStarted nesmí zakázat uložení skutečně doloženého outcome. Ztracený konec zůstává unknown, nezakládat failed podle času ani umělé procento. Neemitovat automaticky žádný nový event z validatoru/store.
- Nepřenášet text/markdown/blocks/tables/visual marks, celé warnings/raw exceptions, rozměry či business výsledek. Žádný artifact resolver/download. Fail-open auditní hranice izoluje i validační/serializační chybu, business tok se nemění.

## Boundaries
Pouze wonderfulkb. Žádný producer hook ani přepis OCR/pipeline/transcribe_scans, žádný cache/queue/retry/lease/execution/business schema change, nové model call, outbox, projekce, deployment či cloud replay. `be-document-processing/.../pipeline.py:89–102` je checked-in sémantická reference odlišná od source `be-validator-agent/pipeline/run.py:125–172,234–248`; nepředstírat shodu se deployed workerem. Nové moduly doménově kvalifikované, bez events.py/state.py/utils.py. Tento kontrakt/store task nedokončuje celý vertikální slice.

## Verification
Implement the TDD cycle using skill:tdd. Focused fake/Moto: native completed, skutečně doložená vision outcome, failed před call s method/model unknown, bezpečný provider error, terminal-only fragment, duplicate, dvě stránky a dva pokusy/runy oddělené; invalid page/attempt/run/duration/business payload bez mutation. Ověřit žádný duplicitní Step terminál a že NoOp/failing audit hranice nemění caller výsledek. Zachovat všechny předchozí eventy a registrované gates. Žádná inference ani AWS, žádná plošná fault matice.


## Přesný původní funkční scope task-8b51eacc-35c1-498a-b4a7-f2421c498bd3
# Monitoring MVP: události skutečně provedené extrakce

## Goal
Existující Step event/store kontrakt přijme začátek a pozorovaný úspěch/selhání kroku extraction, bez ukládání vytěžených hodnot a bez nového typu události. Malá event/store část slice 7.

## Files/functions
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`, existující auditní fail-open hranice podle potřeby; focused `be-document-processing/tests/test_monitor_extraction_events.py`. Proposal `proposal-20261019-150954-c8891f`, sections `slice-extraction`, `instrumentation`; Step allowlist v `plans/tasks/2026-10-20_monitor-mvp-10-source-validation-events.md`. Sémantická reference pouze read-only: `be-document-processing/src/document_processing/pipeline.py:104–111`, `extraction.py:LocalExtractor.extract`.

## Change / exact contract
- Rozšířit existující StepStarted/StepFinished/StepFailed o stage=extraction. Povinné předané run_id a kladný attempt_no, bez page_number. Logický krok scope case/document/run/attempt/stage, stabilní producer-supplied event_id; bez vlastní run/attempt identity nebo odvozování z auditu.
- Allowlist zůstává úzký: skutečně monotónně změřené finite >=0 duration_ms na terminálu; bezpečný technický error_code pouze na StepFailed. Bez nového obecného details/config/result pole, model-call tvrzení nebo počtu vytěžených polí. Nezavádět nové required fields oproti existujícím Step eventům.
- Význam: StepStarted pouze skutečně započatá extrakce nad neprázdným seznamem completed stránek, StepFinished pouze pozorovaný úspěšný návrat, StepFailed pouze skutečně zachycené selhání kroku. Prázdný seznam completed znamená, že se krok neprovedl; nevytvářet skipped/start/success event z absence práce. Platný návrat s prázdnými fields/not_found není automaticky selhání. Lokální extractor není automaticky cloud inference. Tento kontraktový task sám extractor nevolá ani nic neodhaduje z business statusu.
- Ztracený start/AttemptStarted/RunQueued nebrání přijetí doloženého terminálu, ztracený konec unknown. Zachovat conditional event_id idempotenci, document Query a occurred_at jako jediný uložený event timestamp. Všechny změny jsou v interním audit package; business-facing hranice izoluje validaci/serializaci/zápis fail-open.
- Nesmí projít text, fields/hodnoty, quotes/citace, evidence, raw provider responses/errors, celý ExtractionDraft/config/job ani prompt. Chyba jen bezpečný technický kód, bez změny retry rozhodování nebo klasifikace business výsledku.

## Boundaries
Pouze wonderfulkb. Žádný producer hook, změna algoritmu/extractor/worker, model call nebo config, business tabulky/lease/queue/retry/execution změna, outbox, stored projekce/index, deployment/live writes. Checked-in pipeline není doložený nasazený worker; event/store test nedokládá živou extrakci. Doménová jména souborů, ne events.py/state.py/utils.py.

## Verification
Implement the TDD cycle using skill:tdd. Focused fake/Moto: extraction start/finish a start/failure roundtrip, terminal-only fragment, duplicate, dva pokusy/runy oddělené, missing run/invalid attempt/page-scoped extraction/duration/raw business payload odmítnuty bez mutation. Testy významu pracují pouze s explicitně dodanými observations, netvrdí spuštění reálného extractoru; žádné automatické události pro prázdný vstup. NoOp/failing audit boundary nemění caller výsledek. Zachovat source_validation/page/cache kontrakty a všechny registrované gates. Žádná inference, AWS nebo plošná fault matice.


## Přesný původní funkční scope task-2264932c-e1f9-4f8c-9314-3bfffac8234a
# Monitoring MVP: události retry a skutečných konců

## Goal
Event/store část `slice-retry-terminal`, proposal `proposal-20261019-150954-c8891f`: RetryEnqueued, AttemptFinished, RunFinished jako explicitní fakta execution runtime, nikoli rozhodování auditu o business retry.

## Files/functions / contract
`be-document-processing/src/document_processing/audit/audit_events.py`, `audit_storage.py`, fail-open boundary; focused `be-document-processing/tests/test_monitor_retry_terminal_events.py`. Předchozí RunQueued/AttemptStarted kontrakty, reference `pipeline.py:45–58,131–146` pouze sémantická, ne deployed worker proof.
- RetryEnqueued: povinný run_id a kladný attempt_no skutečného odcházejícího pokusu; volitelný bezpečný reason_code pouze doložený producentem. Událost vzniká po potvrzeném enqueue, ne queued statusu nebo příslibu retry. Nový pokus netvrdit před claimem.
- AttemptFinished: run_id, skutečný attempt_no; `attempt_status` completed/partial/failed dle skutečně pozorovaného výsledku pokusu. Konec pokusu není konec runu; může po něm následovat retry. Skutečně měřené duration_ms volitelné finite>=0, bezpečný error_code jen doložený.
- RunFinished: run_id a `run_status` completed/partial/failed; attempt_no pouze pokud známý existující pokus. Max-attempt odmítnutí bez nového claimu může doložit konec runu BEZ smyšleného AttemptStarted/nového attempt_no. Chybějící error_code unknown. RunFinished bez attempt scope je legitimní výjimka, ne povolení vynechat attempt u jiných typů.
- Vše má producer-supplied event_id a dokumentovou obálku, bez page scope. Bez generování identit z počtu audit eventů/SQS receive count. Neodvozovat terminal z ticha, Conflict, lease ztráty, S3-only success nebo partial publish. Bez raw business/provider obsahu, exception/config dumpů a kopií jobu.
- Best-effort fail-open i validace/serializace, conditional idempotence event_id, document partition/occurred_at jediné event-time. Přijmout reorder/terminal-only fragment bez úvodních RunQueued/AttemptStarted; neimplementovat execution state machine uvnitř store ani zakazující cross-event existence checks.

## Boundaries
Pouze wonderfulkb. Žádné producer hooky, enqueue/claim/retry/lease/fencing/business/execution změny, outbox/recovery queue/audit replay, cloud/model/deploy, projekce nebo nový index. Jen contract/store, ne runtime lifecycle integrace. Nové moduly doménové, ne events.py/state.py/utils.py.

## Verification
Implement the TDD cycle using skill:tdd. Focused fake/Moto: retry+AttemptFinished+pozdější jiný AttemptStarted, RunFinished různé outcomes, max-attempt run terminal bez nového pokusu, terminal-only/reorder/duplicate/scope izolace, invalid type/status/scope/duration/raw payload odmítnuty. Store nevyrábí enqueue/claim/AttemptStarted ani RunFinished z jiných eventů. NoOp/failing audit boundary nemění caller; předchozí eventy a registrované gates zachovat. Žádný live retry nebo AWS experiment.


