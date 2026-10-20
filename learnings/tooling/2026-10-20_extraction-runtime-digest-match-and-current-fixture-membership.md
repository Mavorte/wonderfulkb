---
title: "Monitoring: oddělit shodu nasazených OCI bytů od nové opravy a živé fixture"
date: 2026-10-20
category: tooling
component: backend
tags: [monitoring, apprunner, ecr, provenance, fixtures]
file_type: rules
---

Při pokračování extraction read tasku již sibling App Runner rollout skončil SUCCEEDED. ECR BatchGetImage pro aktuální tag odkázal na stejný linux/amd64 manifest a config jako lokálně ověřený image, i když OCI index měl jiný digest kvůli attestation. Taková shoda dokládá nasazené runtime byty původní extrakce; pouhá podobnost tagu nestačí. Pozdější lokální oprava steps cursoru změnila runtime manifest, takže její deployment zůstal samostatně neověřený. Zaznamenat oba stavy a nepřenášet deployed tvrzení na novou candidate. Aktivní/current grant navíc není důkaz aktuální dokumentové membership: následný exact ConsistentRead GetItem vrátil absent a audit Query byl prázdný. Historii nepřepsat, fixture nevyrábět seedem, neodvozovat run/attempt a nepoužít empty200 jako live funkční proof. Před mutací/requesty převzít existující owner guard a shared ledger; mrtvý PID v lock souboru není jejich převzetí.