---
title: "Execution table: scoped update z deployed template"
date: 2026-10-20
category: architecture
component: backend
tags: [cloudformation, dynamodb, trigger, planning, deployment]
file_type: rules
---

# Scoped execution-table update musí vycházet z nasazené šablony

Při plánování task-17168021 obsahoval trigger/template.yaml již ExecutionTable, env a scoped IAM, zatímco runtime handoff popisoval chybějící tabulku i env. Working tree současně obsahoval rozpracované producer/HTTP změny. Existence canonical deklarace proto není důkaz nasazení ani důvod spustit celý deploy.sh.

Pro implementaci připravit candidate z actual deployed Original template a převzít jen ExecutionTable a potřebné env/IAM fragmenty. Zachovat ZIP references, image digests, parametry a mappingy; reviewed change set musí přesně odpovídat allowlistu. Resource readback a producer artifact rollout vykazovat samostatně. Toto je poznatek z plánování, nikoli důkaz provedeného AWS update.

CloudFormation execute neposkytuje Lambda RevisionId CAS. Fresh revision/config porovnání musí doplnit koordinované deployment okno s hostem; konflikt znamená nový inspect/change set, ne overwrite ani out-of-band update bez guardu.
