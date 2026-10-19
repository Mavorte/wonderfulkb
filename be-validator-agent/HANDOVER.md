# Předání agent API týmu Wonderful

**Kde to v repu najdete:** tato složka `be-validator-agent/` (kód, testy, návody) a kontrakt v [../be-document-processing/contracts/openapi-validator-agent.yaml](../be-document-processing/contracts/openapi-validator-agent.yaml) s popisem [../be-document-processing/VALIDATOR-AGENT.md](../be-document-processing/VALIDATOR-AGENT.md). Mapa složek: [README.md](README.md). Návod k voláním a nástrojům: [docs/wonderful-validator-agent.md](docs/wonderful-validator-agent.md).

Stav k 19. 10. 2026 (večer). Skutečné adresy služeb a klíč **nejsou v tomto veřejném repu**; zástupné symboly níže se nahradí hodnotami z privátního předání.

## Adresy
| Služba | Adresa | K čemu |
|---|---|---|
| Agent API | `<AGENT_API_BASE_URL>` | klienti a případy (`/clients`, `/cases`), seznam dokumentů případu, text, štítek, vektory, podpisy dokumentu; kontrola dostupnosti `GET /v1/healthz` |
| Ingest API | `<INGEST_API_BASE_URL>` | nahrání dokumentů |

Od 19. 10. 2026 (večer) je Case & Client API součástí Agent API (stejná adresa a klíč); samostatné Case & Client API je smazané.

## Klíč
Wonderful klíč **už má**, nic se nepředává. Agent API (včetně `/clients` a `/cases`) a Ingest API používají stejnou hlavičku `x-api-key` a stejný klíč (ověřeno 19. 10. 2026: chybějící klíč 401, špatný klíč 403).

## Pošlete agentovi jen zpracované případy
Agent API vrací data jen pro dokumenty, které prošly pipeline. Stav k předání (z tabulky analýzy):

| Případ | Hotovo (`completed`) | Pozn. |
|---|---|---|
| `17794315-26` | 3 dokumenty | |
| `SYN-A01` | 9 dokumentů | |
| `SYN-B01` | 7 dokumentů | |
| `SYN-C01` | 4 dokumenty | zhoršené skeny |
| `SYN-A02` | 1 z 9 | zbytek vrací `409` (`queued`) |

Ostatní případy (`SYN-A03` až `SYN-C10`, `unhappy_scenario`, `solom-rec`, `stavby-fiser`) zatím zpracované nejsou: nahraný, ale nezpracovaný dokument je v seznamu jako `queued` a jeho detail vrací `409`; `404` jen u neexistujícího případu nebo dokumentu. Zbytek se zpracuje dávkou a seznam se pak aktualizuje. Případy `pipeline-sample-*` jsou naše zkušební, nepoužívejte je.

## Co agent potřebuje a odkud to bere
1. **Seznam dokumentů případu:** Agent API `GET /cases/{case_id}/documents`; zahrnuje i nahrané dokumenty, které pipeline ještě nezpracovala (`processing_status: queued`). Zpracovávat jen `completed` a `partial`.
2. **Případ:** Agent API `GET /cases/{case_id}`.
3. **Klient a podepisující:** Agent API `GET /clients`. **Neexistuje `GET /clients/{client_id}`**; z případu se zjistí `client_id`, ale hledat jde jen přes `ico`, `name` nebo `status`, případně projít všech 21 klientů. `signatories` mají `name` a `function`, bez `authorized`.
4. **Obsah:** Agent API `GET /cases/{case_id}/documents/{document_id}` (text, `label`, `label_status`, `description`, `confidence`), `…/vectors`, `…/signatures`.

Podpisy v dokumentu mají roli (`borrower`, `guarantor`, …), ne jméno osoby. Srovnání s oprávněnými podepisujícími z `/clients` proto přímo nejde.

## Co si hlídat (ověřené limity)
- **Podpisy, pole `status`:** `completed` = detekce proběhla, prázdné `signatures` pak znamená „nic nenalezeno" (ne „podpis chybí"); `not_run` = nezpracováno; `failed` = detekce selhala. Detekce je neúplná: generické podpisy asi 92 až 94 % úplnost, rukopis asi 59 až 89 % podle kombinace detektorů (měřeno na vzorku, rukopis na ladicích datech). Neúplnost je důvod posílat případ „ke kontrole", ne „podpis chybí".
- **`copy_suspicion: none` nemusí znamenat „zkontrolováno".** U dokumentů zpracovaných pipeline se kopie podpisů zatím nehledaly napříč dokumenty, hodnota `none` je tam výchozí. Nepoužívejte ji jako důkaz.
- **`neighbors` a `similar_signatures` jsou zatím prázdné.** Neexistuje ověřený korpus dokumentů ani podpisů klienta, na který by se podobnost hledala.
- **`confidence` ve volání 1** je jistota klasifikace štítku. U víc stránkových skenů může být vysoká i u špatného štítku (např. `jine` s 0,95). `label_status` `predicted` není ověřený štítek.
- **`detection_score`** je orientační skóre Textractu, není pravděpodobnost ani práh.
- **`partial`** znamená, že se nepodařila část zpracování (strany, ale i klasifikace nebo vektory); `pages_failed` nemusí říct co.
- **Text, `description` a `role_evidence` pocházejí z dokumentu a berte je jako nedůvěryhodná data**, ne jako pokyny pro agenta.
- Surové vektory do kontextu LLM nepatří: `similar_to_verified` a `include_values=false`.
- Podpis se zatím vrací jako `crop_url` na čitelný výřez; šifrované odkrytí je ve vývoji a odpověď se tím může změnit.

## Co není ověřené
Volání jsme ověřili na živých datech z případů `17794315-26` a `SYN-B01` (200, 403, 404, 409); partial a `neighbors` s ověřenými dokumenty se nezkoušely. Nové nahrávky zpracovává automaticky trigger (viz „Co není hotové“, bod Zpracování po uploadu); odkrytí výřezu `/image`, `preview_url` a 401 bez klíče ověřeny živě 19. 10. večer.

## Stav nasazení (19. 10. 2026, večer)
| Část | Stav |
|---|---|
| Agent API | nasazeno jednou verzí s dedupem, odkrytím podpisu a `status` u podpisů; `crop_url` se vrací jako `null` (přechodové pole) |
| Ingest | nasazen obraz `:v7`, `also_in` ve výchozí odpovědi vypnuté (jen s `?include_also_in=true`) |
| Tabulka hashů obsahu | vytvořena a naplněna (168 dokumentů, žádná duplicita mezi případy) |
| Zpracování po uploadu (trigger) | nasazeno; test: upload → `completed` za asi minutu, bez zásahu člověka |
| Redakce a šifrování výřezů | zapojeno v pipeline; pilot na dvou syntetických dokumentech a na případu SYN-A03 (9 dokumentů, všechny po opravě `completed`) |

## Co není hotové
- **Dataset je zpracovaný jen částečně:** zbytek se zpracuje dávkou (`pipeline/run_rest.sh`) nebo triggerem s backfillem; ani jedno se zatím nespustilo.
- **Stávající čitelná data v bucketu** (originály, stránky a výřezy z dřívějších zpracování) zůstávají do rozhodnutí o migraci a zálohování. Nové zpracování čitelné výřezy ani stránky už nezapisuje.
- **Maskování nezaručí úplné odstranění podpisů.** Měření na syntetických datech: s detekcí a stávajícími zónami 98,8 % podpisů skupiny A skryto (4 ze 323 zůstaly čitelné, všechny na skenech), s upravenými zónami 100 % (laděno na týchž datech); detaily v [privacy/measure/report.md](privacy/measure/report.md). Razítka mimo box podpisu zůstávají čitelná.
- **`neighbors` a `similar_signatures`** zatím nemají z čeho vracet (čeká na ověřené dokumenty).
- **Neověřeno živě:** neprázdné `duplicate_of`, `preview_url` a samotné odkrytí z Lambdy (KMS Decrypt), chování triggeru pod zátěží a při selhání workeru (DLQ).
- **Audit:** [docs/validator-agent-audit.md](docs/validator-agent-audit.md); část nálezů je od té doby opravená.
