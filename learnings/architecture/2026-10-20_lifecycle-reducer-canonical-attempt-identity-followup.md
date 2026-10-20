---
title: "Lifecycle reducer používá canonical attempt identity"
date: 2026-10-20
category: architecture
component: backend
tags: [audit, lifecycle, attempt-identity, pytest]
---

# Lifecycle reducer používá canonical attempt identity

`AttemptFinished` audit observations identifikují pokus kombinací `run_id` a `attempt_no`; výsledek je `attempt_status` (`completed`, `partial`, `failed`). Reducer proto musí seskupovat terminal-only fragmenty podle těchto veřejných scalarů a nesmí očekávat `attempt_id` ani `outcome`.

Při vyhodnocení `AttemptFinished` se obecná událost `finished` nepřičítá jako druhý výsledek, pokud je přítomen konkrétní status. Jeden konzistentní status zůstává jednoznačný, zatímco odlišné statusy terminal observations dávají `ambiguous` a zachovávají evidenci. Při spojování reordered fragmentů lze využít explicitní mapování attempt ID na číslo z další observation stejného runu; pořadí sequence ani čísla se nesmí vydávat za absolutní latest.

Pro ověření použij projektový interpreter z rootu repozitáře. Focused pytest potvrzuje změnu; full suite může být samostatně blokována rozpracovaným event kontraktem v jiné testovací oblasti, a tato collection chyba se nemá opravovat mimo přidělené vlastnictví.
