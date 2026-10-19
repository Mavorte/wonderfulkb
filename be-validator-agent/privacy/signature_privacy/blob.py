"""Šifrovaný blok výřezu.

Formát verze 1 (vše big-endian):

    offset  délka  pole
    0       4      magic  b"WKBS"
    4       1      verze formátu (1)
    5       1      algoritmus (1 = AES-256-GCM)
    6       2      délka obaleného datového klíče N
    8       N      obalený datový klíč (KMS CiphertextBlob, nebo lokální obal)
    8+N     12     nonce
    20+N    …      šifrotext || GCM tag (16 B)

AAD obsahuje hlavičku (magic, verze, algoritmus), obalený klíč a kanonický kontext
(case_id, document_id, signature_id). Změna hlavičky, obalu nebo kontextu proto dešifrování zlomí.
"""
import os
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import context as ctx
from .errors import DecryptionError, PrivacyError
from .keys import KeyProvider, default_provider

MAGIC = b"WKBS"
VERSION = 1
ALG_AES256GCM = 1
_HEADER = struct.Struct(">4sBBH")
NONCE_BYTES = 12
TAG_BYTES = 16
MAX_PLAINTEXT = 20 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _aad(wrapped: bytes, context) -> bytes:
    return _HEADER.pack(MAGIC, VERSION, ALG_AES256GCM, len(wrapped)) + wrapped + ctx.canonical(context)


def encrypt_image(png_bytes: bytes, context, provider: KeyProvider | None = None) -> bytes:
    """Zašifruje PNG výřezu a přiváže ho ke kontextu. Nový datový klíč při každém volání."""
    if not isinstance(png_bytes, (bytes, bytearray)) or not png_bytes:
        raise PrivacyError("Prázdný vstup")
    if len(png_bytes) > MAX_PLAINTEXT:
        raise PrivacyError("Vstup je příliš velký")
    provider = provider or default_provider()
    key, wrapped = provider.generate_data_key(context)
    nonce = os.urandom(NONCE_BYTES)
    ct = AESGCM(key).encrypt(nonce, bytes(png_bytes), _aad(wrapped, context))
    return _HEADER.pack(MAGIC, VERSION, ALG_AES256GCM, len(wrapped)) + wrapped + nonce + ct


def decrypt_image(blob: bytes, context, provider: KeyProvider | None = None) -> bytes:
    """Dešifruje blok; `DecryptionError` při jakékoli chybě (poškození, jiný kontext, klíč, verze)."""
    provider = provider or default_provider()
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
        return AESGCM(key).decrypt(nonce, ct, _aad(wrapped, context))
    except DecryptionError:
        raise
    except InvalidTag:
        raise DecryptionError("Blok nejde dešifrovat") from None
    except PrivacyError:
        raise
    except Exception:  # noqa: BLE001  (nic z vnitřku nevyzradit)
        raise DecryptionError("Blok nejde dešifrovat") from None


def is_encrypted_blob(data: bytes) -> bool:
    return isinstance(data, (bytes, bytearray)) and data[:4] == MAGIC
