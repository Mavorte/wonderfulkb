---
title: "Trigger: opravit cestu kanonické table šablony a zachovat audit při stream variantě"
type: implementation
---
# Trigger: opravit cestu kanonické table šablony a zachovat audit při stream variantě

## Goal
Stream varianta a rollback triggeru zachovají všechny existující zdroje kanonické documents-table šablony; rozdílem bude pouze stream dokumentové tabulky a související output.

## Files/functions
`be-validator-agent/trigger/tests/test_template.py::test_stream_copy_of_the_table_template_differs_only_by_the_stream`, `be-validator-agent/trigger/documents-table-with-stream.yaml`, `be-validator-agent/trigger/deploy.sh` (ORIGINAL_TEMPLATE). Kanonická read-only reference je `be-intake/documents-table/template.yaml`.

## Change
Host při skutečném testu zjistil FileNotFoundError: test hledá neexistující kořenové `documents-table/template.yaml`; deploy.sh má stejně zastaralou relativní rollback cestu. Navíc kanonická šablona obsahuje DocumentsTable + AuditTable a její outputy, stream kopie jen DocumentsTable. Business vlastnosti DocumentsTable jsou jinak shodné po odebrání StreamSpecification. Oprav reference k existujícímu kanonickému owneru a synchronizuj stream variantu tak, aby neztratila AuditTable, Retain/PITR/tags/šifrování ani současné outputy. Regresní test musí ověřovat skutečnou ekvivalenci zdrojů, nikoli jen vypustit audit z porovnání. StreamArn je povolený přidaný output.

## Boundaries
Repo-local soubory výše, vlastní plán/důkazy. Žádné AWS operace, deploy, změny tabulek či dat, replay, model/inference, jiné moduly nebo změny kanonického business schématu. Neodstraňuj zdroje či safety nastavení za účelem zeleného testu. Zachovej ostatní rozpracované změny.

## Verification
Skutečný RED/GREEN na focused testu se stejným argv z trigger cwd: `../../be-document-processing/.venv/bin/python -m pytest -q tests/test_template.py`. Poté celý trigger suite stejným interpreterem a existující registrované gates. Offline ověř správnou rollback cestu; CloudFormation validaci/cfn-lint obou variant proveď dostupným existujícím nástrojem, bez nasazení. Historický host výsledek je `/tmp/wkb-test-0909/trigger-supported.log`; nepředstírej, že původní běh byl úspěšný.
