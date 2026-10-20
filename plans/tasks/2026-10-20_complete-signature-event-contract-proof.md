---
title: "Monitoring signatures: doplnit chybějící důkaz event/store kontraktu"
type: implementation
---
# Monitoring signatures: doplnit chybějící důkaz event/store kontraktu

## Goal
Dokončit pouze neprokázané acceptance scénáře existujícího signature_detection Step event/store kontraktu, proposal proposal-20261019-150954-c8891f / slice-signatures. Zachovat hotové stage/error-code allowlisty a existující funkční testy; nevyrábět druhý audit ani producer integraci.

## Evidence and inputs
Původní brief plans/tasks/2026-10-20_monitor-mvp-18-signature-events.md a plán plans/2026-10-20_task-aa624fc8-7c29-4a9f-9cdc-8b2e7e6acf1e_monitoring-mvp-ud-losti-skute-n-detekce-podpis.md. Implementace be-document-processing/src/document_processing/audit/audit_events.py a audit_storage.py. Focused be-document-processing/tests/test_monitor_signature_events.py má nyní pouze 7 pytest případů: start/completed roundtrip, terminal-only duplicate a pět invalid parametrů. StepFailed se jen konstruuje, neukládá; run/attempt izolace, forbidden payload a explicitní synthetic outcome/fail-open scénáře chybí. Host ověřil 24 focused tests a 244 be-document-processing tests PASS; nejde o důkaz chybějících scénářů ani nezávislou acceptance původního tasku. Zachovat původní RED/GREEN artifact i historické infra_inconclusive.

## Required deliverable
- Rozšířit existující focused test soubor: skutečný signature StepFailed Moto/fake persist/read/decode roundtrip s bezpečným error_code a naměřenou duration, včetně terminal-only případu a idempotence.
- Doložit rozdílné run_id/attempt_no a document partitions bez ztráty či směšování identity, explicitně nepovolit page_number pro signature stage.
- Doložit odmítnutí nepovolených signature/citation/geometry/findings/counts/provider-error/S3/config business payloadů při konstrukci i dekódování dle skutečně platného společného kontraktu, bez store mutation či úniku do logů. Zachovat přísné allowlisty a finite nezápornou duration validaci.
- Reprezentovat požadované synthetic caller outcome scénáře returned-completed-empty, returned-failed, raised-failed, disabled a neznámý/chybějící konec přes existující contract/boundary test seams; neoznačovat syntetický helper za reálný detector/producer. Ověřit NoOp a failing audit boundary bez změny caller návratu/chyby, případně explicitně odlišit již obecně pokryté assertions s konkrétním test path a scénářem. Neimplementovat orchestration jen pro test.
- Nezavádět domnělý production bug: pokud nové testy odhalí skutečnou vadu tohoto společného kontraktu, doložit behaviorální RED a opravit úzce v uvedeném audit event/store scope. Pokud chování již funguje, přiznat characterization-only a nevyrábět falešný RED ani měnit funkční kód jen kvůli TDD.

## Boundaries
Pouze /Users/michal/Projects/wonderfulkb, uvedené audit source/testy a repo-local evidence. Žádné jiné repozitáře/externí config/private data, žádný producer hook/detector/OCR/business změna, AWS/model/deploy/upload/queue/replay, nový store/framework či task lifecycle. Neměnit ostatní hotové testy ani assertion očekávání pro zelený výsledek. Nevytvářet generic events.py/state.py/utils.py; reuse existujících doménově pojmenovaných souborů.

## Verification
Existující skill:tdd pro skutečný production defect; pro doplnění pokrytí pravdivý characterization evidence. Spustit focused testy + celý be-document-processing/tests přes existující odpovídající venv/PYTHONPATH a registrované gates bez ignores/skips/oslabení. Závěr explicitně mapuje jednotlivé výše uvedené požadavky na skutečný test/assertion/command a odlišuje event/store kontrakt od reálných producer/live ověření. Žádné tvrzení že detector nebo deployed signature pipeline byly spuštěny.
