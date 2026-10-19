# Předání agent API týmu Wonderful

**Kde to v repu najdete:** tato složka `be-validator-agent/` (kód, testy, návody) a kontrakt v [../be-document-processing/contracts/openapi-validator-agent.yaml](../be-document-processing/contracts/openapi-validator-agent.yaml) s popisem [../be-document-processing/VALIDATOR-AGENT.md](../be-document-processing/VALIDATOR-AGENT.md). Mapa složek: [README.md](README.md). Návod k voláním a nástrojům: [docs/wonderful-validator-agent.md](docs/wonderful-validator-agent.md).

Stav k 19. 10. 2026 (večer). Skutečné adresy služeb a klíč **nejsou v tomto veřejném repu**; zástupné symboly níže se nahradí hodnotami z privátního předání.

## Adresy
| Služba | Adresa | K čemu |
|---|---|---|
| Agent API | `<AGENT_API_BASE_URL>` | text, štítek, vektory, podpisy dokumentu; kontrola dostupnosti `GET /v1/healthz` |
| Ingest API | `<INGEST_API_BASE_URL>` | autoritativní seznam dokumentů případu `GET /cases/{case_id}/documents`, nahrání dokumentů |
| Case & Client API | `<CASE_API_BASE_URL>` | případ (číslo smlouvy, předmět), klienti vč. podepisujících |

## Klíč
Wonderful klíč **už má**, nic se nepředává. Agent API a Ingest API používají stejnou hlavičku `x-api-key` a stejný klíč (ověřeno 19. 10. 2026: klíč z Ingestu projde na Agent API, špatný klíč dává 403). Case & Client API má vlastní klíč (usage plán `wonderfulkb-demo-plan`), klíč z Ingestu tam dává 403.

## Pošlete agentovi jen zpracované případy
Agent API vrací data jen pro dokumenty, které prošly pipeline. Stav k předání (z tabulky analýzy):

| Případ | Hotovo (`completed`) | Pozn. |
|---|---|---|
| `17794315-26` | 3 dokumenty | |
| `SYN-A01` | 9 dokumentů | |
| `SYN-B01` | 7 dokumentů | |
| `SYN-C01` | 4 dokumenty | zhoršené skeny |
| `SYN-A02` | 1 z 9 | zbytek vrací `409` (`queued`) |

Ostatní případy (`SYN-A03` až `SYN-C10`, `unhappy_scenario`, `solom-rec`, `stavby-fiser`) zatím zpracované nejsou: dokument bez analýzy vrací `404`, případ bez řádku `404 Case neexistuje`, rozpracovaný dokument `409`. Zbytek se zpracuje dávkou a seznam se pak aktualizuje. Případy `pipeline-sample-*` jsou naše zkušební, nepoužívejte je.

## Co agent potřebuje a odkud to bere
1. **Seznam dokumentů případu:** Ingest `GET /cases/{case_id}/documents`. Agent API seznam nevrací; nezpracovaný dokument z ingestu bere agent jako „nezpracováno".
2. **Případ:** Case & Client API `GET /cases/{case_id}`.
3. **Klient a podepisující:** Case & Client API `GET /clients`. **Neexistuje `GET /clients/{client_id}`**; z případu se zjistí `client_id`, ale hledat jde jen přes `ico`, `name` nebo `status`, případně projít všech 21 klientů. `signatories` mají `name` a `function`, bez `authorized`.
4. **Obsah:** Agent API `GET /cases/{case_id}/documents/{document_id}` (text, `label`, `label_status`, `description`, `confidence`), `…/vectors`, `…/signatures`.

Podpisy v dokumentu mají roli (`borrower`, `guarantor`, …), ne jméno osoby. Srovnání s oprávněnými podepisujícími z Case API proto přímo nejde.

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
Volání jsme ověřili na živých datech z případů `17794315-26` a `SYN-B01` (200, 403, 404, 409); partial a `neighbors` s ověřenými dokumenty se nezkoušely. Zpracování nových nahrávek po uploadu nikdo automaticky nespouští (pipeline běží ručně).

## Co není hotové
- **Zpracování po uploadu:** pipeline se spouští ručně (`pipeline/`). Automatický trigger z ingestu je napsaný a otestovaný (`trigger/`), nasazuje se; do té doby nově nahraný dokument nemá analýzu (404 / 409).
- **Zbytek datasetu:** zpracované jsou jen případy v tabulce výše; zbytek čeká na dávku (`pipeline/run_rest.sh`, zatím jen zkontrolovaný syntakticky).
- **Soukromí podpisů:** redakce a šifrování výřezů jsou zapojené v pipeline ([privacy/](privacy/README.md), [pipeline/](pipeline/README.md)) a odkrytí podpisu je v API; na stávající data se zatím nepoužilo. Čitelné výřezy (asi 90), originály a stránky z dřívějších zpracování zůstávají v bucketu do rozhodnutí o migraci a zálohování.
- **Ověřené dokumenty a podpisy klienta:** `neighbors` a `similar_signatures` zatím nemají z čeho vracet.
- **Audit:** nezávislý audit modulů a jeho nálezy jsou v [docs/validator-agent-audit.md](docs/validator-agent-audit.md); část nálezů (např. `copy_suspicion`) je od té doby opravená nebo v opravě.

## Co se mění v nové verzi (kontrakt 0.4.0)
- **Volání 3 (podpisy):** `crop_url` zmizí. Místo něj `preview_url` (zkreslený náhled, 300 s), `reveal_path` a `crop_available`. Čitelný podpis jde jen přes `GET …/signatures/{signature_id}/image` s auditem a `Cache-Control: no-store`. Starší výřezy, které ještě nejsou zašifrované, čitelně nevrací a odkrytí vrací 409.
- **Volání 1 (dokument):** nové `duplicate_of` a `duplicate_relevant`. U šablon (VOP) se duplicita neoznačuje; u individuálních dokumentů (faktura, protokol, objednávka) je to signál „stejný doklad ve dvou financováních".
- **Ingest:** odpověď uploadu má volitelné `also_in`. Zpětně kompatibilní.
