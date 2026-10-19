"""Odkrytí šifrovaného výřezu podpisu: jen dešifrování (KMS Decrypt + AES-256-GCM). Šifrovat tu nelze.

Formát bloku a kontext (AAD) jsou ty z be-validator-agent/privacy/signature_privacy/blob.py (verze 1);
shodu hlídá test_reveal.py (blok zašifrovaný knihovnou `signature_privacy` se tu odkryje a naopak špatný
kontext selže). Knihovna se do Lambdy nebalí, protože tahá Pillow, numpy a PyMuPDF; tady stačí `cryptography`.
Klíče, obsah ani obrázek se nikdy nelogují.
"""
import json
import struct

MAGIC = b"WKBS"
VERSION = 1
ALG_AES256GCM = 1
_HEADER = struct.Struct(">4sBBH")
NONCE_BYTES = 12
TAG_BYTES = 16
CONTEXT_FIELDS = ("case_id", "document_id", "signature_id")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class DecryptionError(Exception):
    """Blok nejde odkrýt (poškozený, jiný kontext, jiný klíč, neznámá verze). Důvod se záměrně nerozlišuje."""


def is_encrypted_blob(data):
    return isinstance(data, (bytes, bytearray)) and bytes(data[:4]) == MAGIC


def context_dict(case_id, document_id, signature_id):
    ctx = {"case_id": case_id, "document_id": document_id, "signature_id": signature_id}
    if not all(isinstance(v, str) and v for v in ctx.values()):
        raise DecryptionError("Neplatný kontext")
    return ctx


def _canonical(ctx):
    return json.dumps(ctx, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


class KmsDecryptor:
    """Obaluje KMS Decrypt: `KeyId` se předává, takže blok zašifrovaný jiným klíčem KMS odmítne.
    `EncryptionContext` ověřuje KMS (a zapíše do CloudTrailu)."""

    def __init__(self, client, key_id):
        self.client, self.key_id = client, key_id

    def decrypt_data_key(self, wrapped_key, context):
        try:
            return self.client.decrypt(CiphertextBlob=wrapped_key, EncryptionContext=dict(context),
                                       KeyId=self.key_id)["Plaintext"]
        except Exception:  # noqa: BLE001  (KMS zamítnutí, špatný kontext, síť: nic dalšího nevyzradit)
            raise DecryptionError("KMS datový klíč neodvinul") from None

    def __repr__(self):
        return f"KmsDecryptor({self.key_id})"


def decrypt_blob(blob, context, provider):
    """PNG z bloku. `provider.decrypt_data_key(wrapped, context_dict)` vrací 32bajtový datový klíč.
    Provider z knihovny `signature_privacy` (LocalKeyProvider) má stejné rozhraní a v testech se použije."""
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        if len(blob) < _HEADER.size + NONCE_BYTES + TAG_BYTES:
            raise DecryptionError("Blok je příliš krátký")
        magic, version, alg, n = _HEADER.unpack_from(blob)
        if magic != MAGIC or version != VERSION or alg != ALG_AES256GCM:
            raise DecryptionError("Neznámý formát bloku")
        body = _HEADER.size + n
        wrapped, nonce, ct = blob[_HEADER.size:body], blob[body:body + NONCE_BYTES], blob[body + NONCE_BYTES:]
        if len(wrapped) != n or len(ct) < TAG_BYTES:
            raise DecryptionError("Blok je poškozený")
        key = provider.decrypt_data_key(wrapped, context)
        aad = _HEADER.pack(MAGIC, VERSION, ALG_AES256GCM, n) + wrapped + _canonical(context)
        return AESGCM(key).decrypt(nonce, ct, aad)
    except DecryptionError:
        raise
    except InvalidTag:
        raise DecryptionError("Blok nejde dešifrovat") from None
    except Exception:  # noqa: BLE001
        raise DecryptionError("Blok nejde dešifrovat") from None
