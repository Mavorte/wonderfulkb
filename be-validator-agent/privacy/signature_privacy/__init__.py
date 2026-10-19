"""Podpisy neukládáme čitelně, ale umíme je ukázat: šifrování výřezů, zkreslený náhled, percepční hash."""
from .blob import MAGIC, VERSION, decrypt_image, encrypt_image, is_encrypted_blob
from .context import SignatureContext
from .errors import DecryptionError, InvalidContext, PrivacyError
from .hashing import hamming, phash
from .keys import (KMS_ALIAS, KeyProvider, KmsKeyProvider, LocalKeyProvider, default_provider,
                   set_default_provider)
from .preview import distorted_preview
from .redact import Region, changed_outside, conservative_regions, redact_pdf, redact_png, verify_redacted
from .reveal import api_key_id, audit, reveal_signature

__all__ = ["MAGIC", "VERSION", "KMS_ALIAS", "SignatureContext", "KeyProvider", "KmsKeyProvider",
           "LocalKeyProvider", "PrivacyError", "InvalidContext", "DecryptionError", "encrypt_image",
           "decrypt_image", "is_encrypted_blob", "distorted_preview", "phash", "hamming", "default_provider",
           "set_default_provider", "api_key_id", "audit", "reveal_signature", "Region", "conservative_regions", "redact_pdf", "redact_png",
           "verify_redacted", "changed_outside"]
