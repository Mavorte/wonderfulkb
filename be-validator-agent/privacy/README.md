# privacy: podpisy neukládáme čitelně, ale umíme je ukázat

Knihovna `signature_privacy` pro funkci „výřez podpisu se ukládá šifrovaně, běžně se ukazuje zkreslený náhled, čitelný jen na vyžádání s auditem“. Inventura, model hrozeb, doporučení co šifrovat a návrh změn kontraktu a `store.py`: [be-validator-agent/docs/validator-agent-privacy.md](../../../be-validator-agent/docs/validator-agent-privacy.md). **Nic z toho není nasazeno a v bucketu se nic nezměnilo.** KMS klíč `alias/wonderfulkb-signatures` existuje (vytvořila ho nadřazená session se souhlasem uživatele); konfigurace `PRIVACY_KMS_KEY_ID`.

| Funkce | Co dělá |
|---|---|
| `encrypt_image(png, context, provider=None) -> bytes` | AES-256-GCM, nový datový klíč na každý výřez (envelope), AAD = hlavička + obalený klíč + `case_id`/`document_id`/`signature_id` |
| `decrypt_image(blob, context, provider=None) -> bytes` | `DecryptionError` při poškození, jiném kontextu, klíči i verzi (důvod se nerozlišuje) |
| `distorted_preview(png) -> bytes` | PNG s hrubou mřížkou (≤ 10 buněk na šířku), rozmazané; smí se ukazovat bez odkrytí |
| `phash(png) -> str \| None` | 64 bitů, hex 16 znaků; stejný postup jako `signatures/…/imaging.py`, jednosměrný, jen kopie |
| `KeyProvider`, `KmsKeyProvider`, `LocalKeyProvider` | KMS `GenerateDataKey`/`Decrypt` (kontext jde do `EncryptionContext`), lokální hlavní klíč pro testy |
| `conservative_regions`, `redact_pdf`, `verify_redacted`, `changed_outside`, `redact_png` | zamaskování podpisových oblastí v PDF a PNG (opravdová redakce, ne překrytí) a ověření, že pod oblastí nic nezbylo; vyžaduje PyMuPDF |
| `reveal_signature(...)`, `api_key_id(...)`, `audit(...)` | pomocníci pro handler odkrytí: čtení z S3, dešifrování, auditní JSON řádek |

Formát bloku (verze 1): `WKBS | verze | alg | délka obalu | obalený klíč | nonce 12 B | šifrotext+tag` (podrobně v `blob.py`).

## Použití

```python
from signature_privacy import (SignatureContext, KmsKeyProvider, LocalKeyProvider,
                               encrypt_image, decrypt_image, distorted_preview, phash)

provider = KmsKeyProvider()                 # alias/wonderfulkb-signatures, region eu-central-1
# vývoj a testy bez AWS: provider = LocalKeyProvider.generate()   (nebo from_env: WKB_LOCAL_MASTER_KEY, base64 32 B)
ctx = SignatureContext(case_id, document_id, "sig_01")

blob = encrypt_image(png, ctx, provider)    # do S3 jako signatures/sig_01.png.enc
preview = distorted_preview(png)            # do S3 jako signatures/sig_01.preview.png
h = phash(png)                              # do signatures.json
png_again = decrypt_image(blob, ctx, provider)
```

Bez `provider` se použije výchozí: `PRIVACY_KMS_KEY_ID` (alias nebo ARN) → KMS (`KmsKeyProvider()` bez argumentu míří na `alias/wonderfulkb-signatures`), jinak `WKB_LOCAL_MASTER_KEY`, jinak chyba (nikdy tiché použití slabšího klíče). `set_default_provider()` ho nastaví z kódu. Žádný klíč není v repozitáři; chyby ani logy neobsahují klíče, data ani identifikátory z chybných pokusů.

## Testy

```bash
python -m venv venv && venv/bin/pip install --only-binary :all: -r requirements-dev.txt
venv/bin/python -m pytest        # 63 testů, bez AWS (KMS a S3 přes moto); redakce vyžaduje PyMuPDF

# živý KMS (jen syntetická data, nic se nikam nezapisuje):
AWS_PROFILE=hackathon PRIVACY_KMS_KEY_ID=alias/wonderfulkb-signatures venv/bin/python live_check.py
```

`pymupdf` je pro redakci povinný a pro testy volitelný: bez něj se přeskočí testy redakce a test, že `phash` dává stejné hodnoty jako `signatures/signature_pipeline/imaging.py`. Testy samy přepíšou přihlašovací údaje fiktivními, takže na skutečný účet nesáhnou. Moto nastartuje pomalu (jednotky sekund na fixturu).

## Co je ověřeno a co ne

Ověřeno (testy s lokálním klíčem a mockem):
- round-trip, nový nonce i klíč při každém volání, žádný čitelný obsah v bloku;
- špatný kontext (každé ze tří polí), špatný klíč, jakýkoli změněný bajt bloku, useknutý blok, neznámá verze, čitelný PNG místo bloku: vždy `DecryptionError`; neplatný kontext: `InvalidContext`;
- náhled: žádná ostrá hrana, dva podpisy se stejným hrubým rozložením inkoustu dávají skoro stejný náhled, obsah leží blízko hrubé mřížky, prázdný výřez zůstane světlý;
- `phash`: stabilní, drží posun a změnu měřítka, odliší jiné podpisy, prázdný výřez `None`, shoda s modulem podpisů;
- `KmsKeyProvider` proti moto: round-trip přes alias, `AES_256` a `EncryptionContext` v požadavku, jiný klíč nebo jiný kontext selže; odkrytí včetně auditu (`revealed` / `denied` / `error`).

Ověřeno živě (19. 10. 2026, `live_check.py`): `KmsKeyProvider` proti skutečnému klíči: round-trip, jiný `case_id`/`document_id`/`signature_id` odmítnut. Redakce spuštěná lokálně na 16 vzorových PDF: `verify_redacted` bez problémů, změna mimo oblasti do 0,32 % pixelů strany.

Neověřeno:
- **IAM a politika klíče**: oprávnění rolí (API smí `Decrypt`, pipeline jen `GenerateDataKey`) jsou jen navržená v docs, latence a limity KMS pod zátěží;
- **úplnost zamaskování**: redakce odstraní nálezy a zóny u popisků, ale podpis mimo ně zůstane (test to hlídá); kolik jich zůstane na skutečných datech, nikdo nezměřil;
- napojení do `signatures/store.py`, Lambdy `api/` a pipeline (jen návrh v docs);
- čitelnost náhledu pro lidské oko na skutečných podpisech (testy jsou na syntetických) a odolnost vůči pokročilé rekonstrukci;
- výkon: jedno volání KMS na výřez.

## KMS klíč

Klíč už existuje; `create_key.sh` zůstává jako dokumentace, jak vznikl (suchý běh, `CONFIRM=yes` pro skutečné vytvoření, idempotentní), a nespouští se znovu. Klíč nejde okamžitě smazat, jen naplánovat smazání na 7 až 30 dní. IAM práva (odkrytí jen API, pipeline jen `GenerateDataKey`): docs, část 7.
