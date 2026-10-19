---
title: "Case Client: SAM šablona není in-place deploy existující služby"
date: 2026-10-19
category: tooling
component: ci-cd
tags: [case-client, sam, lambda, planning, in-place]
file_type: decisions
---

Při plánování task-0c4b4cd5-64c3-4bb1-a2dd-a3f712a2fb3f bylo ze souboru be-case-client/template.yaml ověřeno, že FunctionName obsahuje AWS::StackName a šablona vlastní nové API, execution role a API key. Pro autorizované nahrazení existující wonderfulkb-case-client na původním REST API proto nepoužívat sam deploy této šablony. Zachovat ji pro offline lint a samostatný artefakt; in-place postup musí explicitně snapshotovat původní Zip/config, použít Lambda UpdateFunctionCode/UpdateFunctionConfiguration s RevisionId a ověřit CodeSha256 před i po HTTP přejímce. Na macOS arm64 navíc nativní build nezaručuje Linux x86_64 kompatibilitu připnutého simplejson; plán vyžaduje CPython3.13 manylinux x86_64 wheels a kontrolu binárního formátu. Toto je poznatek z read-only plánování a inspekce zdrojů, nikoli důkaz uskutečněného deploye nebo funkčního cloudového transportu.