---
title: "Case Client: plánovací retry nesmí obnovit vyčerpaný live budget"
date: 2026-10-19
category: architecture
component: backend
tags: [case-client, planning, retry, budgets, evidence]
file_type: rules
---

Při plánovacím retry pro task-beca6825-147b-43d9-9fb6-694368e70948 již existovaly deploy/HTTP nástroje i offline guard testy, přestože starý plán tvrdil opak. Manifest evidoval pět deploy pokusů, čtyři fixtures, jeden neověřený POST a ověřený rollback na Node.js. Nová session není nový live budget: zachovat ledger, nepovolit šestý deploy ani nový run_id jako obcházení limitu. Pokračování může připravit offline opravy a review; další cloudové mutace potřebují nové výslovné zadání s rozpočtem a vyřešeným přístupem. Starší review porovnat s aktuálním kódem, protože některé opravy už mohou existovat; nezačínat znovu již zelené TDD guardy. Pro nový focused RED vybrat dosud nechráněnou hranici, například vypršení deadline během čekání HTTP limiteru. Tato session pouze četla lokální podklady a aktualizovala plán; žádný aktuální AWS readback ani ověření runtime neprovedla.