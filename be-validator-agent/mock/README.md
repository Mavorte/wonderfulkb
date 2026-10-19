# Mock Validator Agent API

Mock podle [be-document-processing/contracts/openapi-validator-agent.yaml](../../be-document-processing/contracts/openapi-validator-agent.yaml). Bez závislostí, stačí Python 3.

```bash
API_KEY=mock-key PORT=8080 python3 server.py
curl -H 'x-api-key: mock-key' localhost:8080/v1/_mock/cases     # seznam case_id a document_id
```

Server poslouchá jen na `127.0.0.1`; na všech rozhraních (`0.0.0.0`, např. v Dockeru) jen s výslovným `MOCK_BIND_ALL=1`. Interní chyba vrací 500 s obecným textem, detail jde jen do logu serveru.

Test proti spec (`pip install pyyaml jsonschema`): `BASE_URL=http://localhost:8080/v1 python3 contract_test.py`

## Data
- **Texty** se čtou z textových výpisů vzorových dokumentů z hackathonového balíku (nejsou v repu): složka `vzorove-dokumenty` v `WONDERFULKB_SAMPLES_DIR` (nebo `TEXT_DIR` na podsložku `text`). Bez nich mock běží a vrací dokumenty bez textu. Jsou to bankovní dokumenty, mock s nimi nenasazovat mimo schválené prostředí.
- **Štítky** se odvozují z prefixu souboru (taxonomy.yaml v repu není). `0_`/`2_`/`99_` jsou `verified`, ostatní `predicted`.
- **Vektory** (text, obraz i podpis mají 1024 dimenzí) jsou deterministické: stejný štítek ≈ 0,8 podobnosti, různý ≈ 0. `neighbors` počítá kosinus nad ověřenými dokumenty včetně syntetického `ref-corpus`.
- **Podpisy** vznikají podle typu dokumentu (role + `role_evidence`), `preview_url` ukazuje na PNG z mocku (a stejný PNG vrací `reveal_path`); `crop_url` už není (spec 0.3.0).
  Odpověď volání 3 nese povinné `status`: `completed` u zpracovaných dokumentů (prázdné `signatures` = nic nenalezeno), `not_run` u nezpracovaných (např. `processing`). `failed` mock nevrací.

## Připravené scénáře
| Situace | Kde |
|---|---|
| `partial`, `pages_failed` 4–9 | Stavby Fišer, `10_…Objednávka + TS` |
| `409` (`processing`) | Solom Rec, `11_…Protokol` |
| `confidence: null` | Solom Rec `10_…`, oba dokumenty `99_` |
| `copy_suspicion: suspected` (stejný podpis ve smlouvě a v potvrzení o převodu) | Stavby Fišer, `0_F_Smlouva` ↔ `11_…` |
| `signatures: []` | dokumenty `99_`, `14_`, `10_` |
| `status: not_run` (volání 3, `signatures: []` není nález) | Solom Rec, `11_…Protokol` |
| `403` / `404` / `400` | špatný klíč / neznámé id / špatný parametr |

Mimo spec jsou jen `/healthz` (a `/v1/healthz` jako u reálného API, bez klíče) a `/v1/_mock/*`.
