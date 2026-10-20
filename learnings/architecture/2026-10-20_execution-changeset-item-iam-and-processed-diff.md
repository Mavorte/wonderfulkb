---
title: "Execution deployment: item-level IAM a úplný Processed diff"
date: 2026-10-20
category: architecture
component: backend
tags: [cloudformation, dynamodb, iam, execution, deployment, recovery]
file_type: rules
---

# Execution deployment: ověřovat item-level IAM a celý Processed diff

Při přípravě deploymentu execution tabulky task-17168021 již lokální canonical SAM definoval resource a transactional policy, ale skutečný stack tabulku ani bindings neměl. Nasazená šablona navíc obsahovala CasesTable/webhook konfiguraci, která v lokální dirty šabloně nebyla; plošný deploy by proto nebyl bezpečná úzká změna.

Kandidát byl odvozen z deployed Original SAM a převzal pouze canonical tabulku a odůvodněné enqueue/worker env a IAM fragmenty. Native změnová sada měla přesně pět resources: Add ExecutionTable a non-replacement Modify dvou Function Environment a dvou Role Policies. Celý Processed template byl porovnán s původním: po odečtení přesně povolených additions musel každý původní resource/property i top-level struktura zůstat identická. Samotné Scope=Properties nebo Replacement=False nestačí k prokázání úzkého diffu; IAM kontext v DescribeChangeSet může být navíc zkrácený, proto je potřeba GetTemplate pro Processed candidate.

Source `dynamodb:TransactWriteItems` není náhradou za oprávnění k jednotlivým operacím transakce. Skutečný ledger provádí ConditionCheck na analysis/execution, Put a Update. Kandidát proto zachoval analysis Get/Put/Update a doplnil execution Get/Put/Update, ConditionCheckItem na obou konkrétních tabulkách a audit Put pouze na audit ARN. Referenční kontrakt AWS: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis-iam.html . DLQ nevolá ledger/audit, proto nepotřebuje automaticky stejné grants jako producer callers.

Read-only control-plane test může zachytit genuine resource RED bez business seedů: ověřit STS, DescribeTable, schema, billing, PITR a stack ownership. Zde helper správně zachytil absenci tabulky. GREEN musí přijít až po skutečném deployi, nikoli po lokální validaci candidate. V této session byla změnová sada pouze připravena a reviewována; čekala na plánem předepsané potvrzené výlučné deployment okno, protože CFN nemá Lambda RevisionId CAS. Tento learning není tvrzení, že tabulka existuje nebo že producer rollout funguje.

Recovery config ukládat chráněně a gitignored; původní ZIP ověřit skutečným SHA256 vůči oběma deployed CodeSha256 a dostupnost image přes immutable ECR digest. Do běžné evidence patří jen reference, hashe a povolené rozdíly, nikoli celé environment/policy objekty.
