---
title: "Case Client: plán ověřuje aktuální root ignore bez host excludes"
date: 2026-10-19
category: tooling
component: tooling
tags: [case-client, planning, gitignore, acceptance]
file_type: rules
---

# Aktualizace plánu po hostově změně ignore pravidel

Při navazujícím plánování znovu čti aktuální `.gitignore` a kanonický plán: plán může stále popisovat staré čtyři výjimky, zatímco host již mezitím připravil širokou root policy. Nevracej jej k původnímu stavu a netvrď, že chybí pravidla pouze podle dřívějšího auditu.

V plánu pro přejímku specifikuj fixture s pouze zkopírovaným root `.gitignore` bez host-local/global Git excludes. Ověř pozitivní build/cache/env vzorky i negativní zdroje, důkazy, dokumentaci a `.env` příklady; skutečný index a `.git` repozitáře zůstanou nedotčené. Nested Wonderful publikační ignore politika může mít jiné požadavky na dist bundly.
