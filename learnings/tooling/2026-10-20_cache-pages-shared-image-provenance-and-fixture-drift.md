---
title: "Sdílený deployed image vyžaduje časově přesnou provenance a aktuální membership"
date: 2026-10-20
category: tooling
component: backend
tags: [monitoring, docker, provenance, concurrency, cache, authorization]
---

# Ověření sdíleného image je časově omezený snapshot

Při pokračování cache-pages read tasku může jiný native owner již nasadit tentýž runtime artifact. Porovnat nejen tag/index, ale také amd64 manifest, config digest a source aggregate včetně untracked souborů. Dva lokální buildy mohou mít jiný OCI index kvůli attestation, přesto stejný spustitelný manifest/config. Přesný ECR digest lze stáhnout a přímo v něm spustit ASGI smoke přes stdin (`docker run -i --network none --entrypoint python IMAGE - < smoke.py`), bez source mountů. Ověřit UID10001 a audit import ze site-packages.

Na konci znovu porovnat konkrétní source hashes: během této kontroly souběžný owner změnil steps cursor, zatímco cache page/auth/mapper/reader zůstaly shodné s nasazeným image. Původní whole-source equality platí jen k času buildu. Pozdější cizí změnu zachovat, neoznačit ji za nasazenou a nepřepsat rolloutem. Cílená cache+steps regrese po tomto driftu prošla40 testy.

Artifact smoke není live fixture proof. I exact active token/grant může odkazovat na dokument, jehož aktuální metadata už chybí. Dva strongly-consistent projected GetItem a autentizovaný document-events404/private,no-store tento blocker potvrdily. Neodvozovat run/attempt z vymyšlených IDs, neobcházet membership pomocí auditu a nevyrábět seed/replay. Uvést čas a zachovat zbývající task ledger (zde1/12 GET), dokud owner neposkytne legitimní observation. Zachovat původní pravý TDD cyklus; nevyrábět nový RED odstraněním hotového allowlistu.
