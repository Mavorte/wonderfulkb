# apps/backoffice

Backoffice aplikace pro Wonderful: výběr klienta a založení case. Zdrojový kód aplikace je v [app](app/README.md). Složky `functions/` a `tables/` jsou zatím prázdné.

Založení case (`app/src/cases/createCase.ts`) je zatím mock a nic neukládá. Skutečné API: `POST /cases` (case-client, viz [quick-connect](../../docs/quick-connect.md)). `case_id` přiděluje služba, aplikace ho nezadává.

Nasazení a pravidla práce: [AGENTS.md](AGENTS.md).
