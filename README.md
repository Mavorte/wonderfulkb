## Wonderful KB Hackaton

Backoffice pro kontrolu firemních úvěrových dokumentů: výběr firmy podle názvu/IČO, trvalé případy, nahrání souborů, OCR, doložené vytěžení a kontroly napříč dokumenty.

- `apps/backoffice/app/`: React UI s výběrem firmy, dokumenty, stavem zpracování, přepisem, náhledy a ručními opravami.
- `be-case-client/`: původní kontrakt firem a případů; jeho cloudová implementace je samostatná komponenta.
- [`be-document-processing/README.md`](be-document-processing/README.md): spuštění backendu, API kontrakty, testy a AWS šablona.

OCR používá AWS Bedrock **výhradně ve Frankfurtu (`eu-central-1`)**. Výchozí model je Qwen3 VL přes Mantle; alternativa Gemma 4 31B má vlastní podporovanou API cestu. Přihlašovací údaje AWS zůstávají na serveru.

U PDF výchozí režim nejdříve získá text a pozice přes Python/PyMuPDF, po jednotlivých stránkách. Použitelný text pokračuje do LLM extrakce. Skeny, obrázky a stránky s nepoužitelnou textovou vrstvou se přepisují pomocí Bedrock vision LLM. Volba „Vše vizuálně přes Bedrock“ vynutí obrazový přepis každé stránky.

Lokální vývoj: spusťte dokumentový backend podle jeho README. Potom v `apps/backoffice/app` proveďte `pnpm install` a `pnpm runner` (Node.js 24+ kvůli serverovému TypeScript proxy modulu). Dokumentové požadavky `/document-api/*` přeposílá runner na `DOCUMENT_API_URL` (výchozí `http://127.0.0.1:8010`). `DOCUMENT_API_KEY` a případné `CASE_CLIENT_API_URL`/`CASE_CLIENT_API_KEY` jsou serverové proměnné. Použijte runner; samostatný statický `pnpm dev` nepřipojuje backend.

Pro nasazenou Wonderful aplikaci musí host zajistit stejnou **autentizovanou serverovou proxy** `/document-api/*` na obě AWS API; samotný upload frontendového bundle tuto routu nevytvoří. Lokální runner není produkční autentizační brána. API klíč se nevkládá do prohlížeče ani do Vite proměnných.

Závislost `@wonderful/ui-base` vyžaduje přihlášení do privátního Wonderful registru podle `apps/backoffice/app/AGENTS.md`. Veřejný npm ji neposkytuje.
