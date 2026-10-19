# Ověření implementace – 19. 10. 2026

- Python 3.10: `python -m pytest be-document-processing/tests -q` – **32 testů prošlo**. HTTP integrace, evidence a role, ruční opravy, opakování úloh, PDF-first přepínání, Mantle SigV4 a AWS adaptéry přes Moto. Jedno upozornění Starlette na budoucí změnu testovacího HTTP klienta.
- `openapi-spec-validator contracts/openapi-ingest.json` – **OK**.
- `cfn-lint template.yaml` – **bez nálezů**. SAM infrastruktura nebyla nasazena; container build není ověřen.
- Frontend s Node.js 24.22.0 a veřejnými závislostmi podle původního lockfile: `pnpm test` – **4 testovací soubory prošly**; `pnpm build` – **prošel** včetně TypeScript kontroly.
- Plný `pnpm install` a `pnpm build:runner` **blokuje privátní `@wonderful/ui-base@0.100.0`**. Veřejný npm vrací 404; je nutné přihlášení do Wonderful registru. Pro ověření běžného bundle byly veřejné nástroje instalovány do odděleného adresáře. Balíček ui-base nebyl nahrazen, jeho verze a původní lockfile zůstaly zachovány.
- V tomto prostředí není nakonfigurovaný AWS profil. **Nebyla spuštěna živá inference ani upload dokumentů do AWS.** Kvalita OCR, skutečná dostupnost modelu v účtu, latence a náklady zatím nejsou změřené.

Produkční připojení Wonderful hostu vyžaduje autentizovanou serverovou proxy popsanou v kořenovém README. Lokální runner ji poskytuje pouze pro vývoj. Dokumentová služba čte existující cloudové firmy a případy, jejich backend neimplementuje.
