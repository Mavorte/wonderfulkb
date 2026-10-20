---
title: "Audit workeru musí zachovat warm dependency a doložit celý publish boundary"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, worker, warm-options, publication, dedup, tdd]
file_type: rules
---

Ve WonderfulKB trigger workeru nesmí integrační audit kopírovat warm Options pomocí dataclasses.replace: pipeline.get_vision ukládá lazy provider a jeho rate limiter do Options. Kopie na každém dokumentu resetovala cache; skutečný dvoudokumentový entrypoint test zachytil dvě konstrukce provideru namísto jedné. Předávat audit_listener_factory explicitním keyword-only argumentem run_document a immutable execution_context odděleně. Warm Options obsahuje dependency, nikoli per-run identitu.

Dedup reuse_analysis má business best-effort kopírování PNG stránek: CopyObject ClientError pouze zaloguje a vrátí completed row spolu s reportem pages_copied. Samotný completed návrat proto nedokládá úplnou publication. Auditní _finish_reused musí ověřit pages_copied proti page_count; při rozdílu zachovat původní business writes/result, ale emitovat publication failure a žádný ResultPublished ani RunFinished. Genuine TDD musí spustit první skutečný worker pro origin, skutečný hash index/find_source/reuse_analysis pro target a fake pouze S3 transport; nepřipravovat audit DTO ručním seedem.

Dále se vyhnout kolizi jména dispatch parametru method s veřejným page field method. Listener lookup/factory/metodu izolovat ve fail-open boundary, včetně volání po business commitu. Task b0db5177 zachytil všechny tyto vady skutečnými behaviorálními RED/GREEN cykly. Lokální test a Docker build nadále neprokazují deployed worker: import finálního image může být zablokovaný Docker no-space ještě před Pythonem; neoznačovat takový stav installed green a nemazat cizí recovery cache.