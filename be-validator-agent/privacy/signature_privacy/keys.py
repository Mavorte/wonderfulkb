"""Správa klíčů: envelope šifrování. Datový klíč je pro každý blok nový, obalený hlavním klíčem.

`KeyProvider.generate_data_key(context)` vrátí (čistý klíč, obalený klíč); `decrypt_data_key(wrapped, context)`
vrátí čistý klíč. Kontext se předává i obalování, takže obalený klíč nejde použít pro jiný podpis.
Nic z toho se nesmí logovat.
"""
import base64
import os
from abc import ABC, abstractmethod

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import context as ctx
from .errors import DecryptionError, PrivacyError

KEY_BYTES = 32
KMS_ALIAS = "alias/wonderfulkb-signatures"


class KeyProvider(ABC):
    @abstractmethod
    def generate_data_key(self, context) -> tuple[bytes, bytes]:
        """(plaintext_key[32], wrapped_key)."""

    @abstractmethod
    def decrypt_data_key(self, wrapped_key: bytes, context) -> bytes:
        """Plaintext_key; `DecryptionError`, když nejde (špatný klíč, kontext, poškozený obal)."""


class LocalKeyProvider(KeyProvider):
    """Hlavní klíč v paměti. Jen testy a lokální vývoj, ne produkce (klíč leží v procesu, bez auditu).

    Klíč se předává zvenku (`from_env`) nebo vzniká náhodně (`generate`); do repozitáře nepatří."""

    ENV = "WKB_LOCAL_MASTER_KEY"

    def __init__(self, master_key: bytes):
        if not isinstance(master_key, (bytes, bytearray)) or len(master_key) != KEY_BYTES:
            raise PrivacyError("Hlavní klíč musí mít 32 bajtů")
        self._master = AESGCM(bytes(master_key))

    @classmethod
    def generate(cls) -> "LocalKeyProvider":
        return cls(os.urandom(KEY_BYTES))

    @classmethod
    def from_env(cls, name: str = ENV) -> "LocalKeyProvider":
        raw = os.environ.get(name)
        if not raw:
            raise PrivacyError(f"Proměnná {name} není nastavena")
        try:
            return cls(base64.b64decode(raw, validate=True))
        except ValueError:
            raise PrivacyError(f"Proměnná {name} nemá platný base64") from None

    def generate_data_key(self, context):
        key = os.urandom(KEY_BYTES)
        nonce = os.urandom(12)
        return key, nonce + self._master.encrypt(nonce, key, ctx.canonical(context))

    def decrypt_data_key(self, wrapped_key, context):
        try:
            return self._master.decrypt(wrapped_key[:12], wrapped_key[12:], ctx.canonical(context))
        except (InvalidTag, ValueError):
            raise DecryptionError("Datový klíč nejde odvinout") from None

    def __repr__(self):
        return "LocalKeyProvider(<skryto>)"


class KmsKeyProvider(KeyProvider):
    """Envelope šifrování přes AWS KMS: `GenerateDataKey` (AES_256) a `Decrypt`.

    `key_id` je alias nebo ARN (výchozí `alias/wonderfulkb-signatures`). Kontext jde do `EncryptionContext`,
    takže ho KMS ověřuje také a objeví se v CloudTrailu (jsou to jen identifikátory, ne obsah)."""

    ENV = "PRIVACY_KMS_KEY_ID"

    def __init__(self, key_id: str | None = None, client=None, region: str = "eu-central-1"):
        key_id = key_id or os.environ.get(self.ENV) or KMS_ALIAS
        if client is None:
            import boto3
            client = boto3.client("kms", region_name=region)
        self.key_id, self.client = key_id, client

    def generate_data_key(self, context):
        r = self.client.generate_data_key(KeyId=self.key_id, KeySpec="AES_256", EncryptionContext=ctx.normalize(context))
        return r["Plaintext"], r["CiphertextBlob"]

    def decrypt_data_key(self, wrapped_key, context):
        try:
            r = self.client.decrypt(CiphertextBlob=wrapped_key, EncryptionContext=ctx.normalize(context),
                                    KeyId=self.key_id)
        except self.client.exceptions.ClientError:
            raise DecryptionError("KMS datový klíč neodvinul") from None
        return r["Plaintext"]

    def __repr__(self):
        return f"KmsKeyProvider({self.key_id})"


_default: KeyProvider | None = None


def set_default_provider(provider: KeyProvider | None) -> None:
    global _default
    _default = provider


def default_provider() -> KeyProvider:
    """Nastavený výchozí provider, jinak podle prostředí: `PRIVACY_KMS_KEY_ID` (KMS), jinak `WKB_LOCAL_MASTER_KEY`.

    Bez nastavení se vyhodí chyba, nikdy se potichu nepoužije slabší klíč."""
    global _default
    if _default is None:
        if os.environ.get("PRIVACY_KMS_KEY_ID"):
            _default = KmsKeyProvider(os.environ["PRIVACY_KMS_KEY_ID"])
        elif os.environ.get(LocalKeyProvider.ENV):
            _default = LocalKeyProvider.from_env()
        else:
            raise PrivacyError("Není nastaven KeyProvider (PRIVACY_KMS_KEY_ID nebo WKB_LOCAL_MASTER_KEY)")
    return _default
