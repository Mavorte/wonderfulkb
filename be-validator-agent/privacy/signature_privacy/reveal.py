"""Odkrytí podpisu na vyžádání: čtení šifrovaného bloku z S3, dešifrování, auditní záznam.

Používá handler Lambdy (`GET .../signatures/{signature_id}/image`). Identifikátory case, dokumentu a podpisu
se berou z cesty požadavku, ne z JSON dokumentu, ať je kontext (AAD) nejde podstrčit.
"""
import hashlib
import json
import logging
import time

from .blob import decrypt_image
from .context import SignatureContext
from .errors import DecryptionError

log = logging.getLogger("wonderfulkb.privacy.audit")
CACHE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache", "Content-Type": "image/png",
                 "X-Content-Type-Options": "nosniff"}


def api_key_id(request_context=None, api_key=None):
    """Identifikátor volajícího bez odhalení klíče: `apiKeyId` z API Gateway, jinak otisk (SHA-256, 12 znaků)
    předloženého klíče. Samotný klíč se nikdy nevrací ani neloguje."""
    ident = ((request_context or {}).get("identity") or {})
    if ident.get("apiKeyId"):
        return ident["apiKeyId"]
    if api_key:
        return "fp:" + hashlib.sha256(api_key.encode()).hexdigest()[:12]
    return "unknown"


def audit(caller, context, outcome, request_id=None, logger=None):
    """Jeden JSON řádek: kdo, kdy, který podpis, výsledek. Žádný obsah, klíče ani obrázek."""
    ctx = SignatureContext(**context) if isinstance(context, dict) else context
    rec = {"event": "signature_reveal", "caller": caller, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "case_id": ctx.case_id, "document_id": ctx.document_id, "signature_id": ctx.signature_id,
           "outcome": outcome, "request_id": request_id}
    (logger or log).info(json.dumps(rec, ensure_ascii=False))
    return rec


def reveal_signature(s3, bucket, key, context, provider, caller, request_id=None, logger=None):
    """Vrátí dešifrovaný PNG. Auditní záznam se zapíše před vrácením dat (i při selhání, s výsledkem `denied`
    nebo `error`)."""
    try:
        blob = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except Exception:  # noqa: BLE001
        audit(caller, context, "error", request_id, logger)
        raise
    try:
        png = decrypt_image(blob, context, provider)
    except DecryptionError:
        audit(caller, context, "denied", request_id, logger)
        raise
    audit(caller, context, "revealed", request_id, logger)
    return png
