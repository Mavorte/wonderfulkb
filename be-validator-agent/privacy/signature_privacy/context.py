"""Kontext, ke kterému je šifrovaný výřez přivázaný (AAD)."""
import json
from typing import Mapping, NamedTuple

from .errors import InvalidContext


class SignatureContext(NamedTuple):
    case_id: str
    document_id: str
    signature_id: str


FIELDS = SignatureContext._fields


def normalize(context) -> dict:
    """Vrátí {case_id, document_id, signature_id} jako řetězce. Přijme SignatureContext nebo dict.

    Další klíče se odmítnou: každé pole navíc by se tiše stalo součástí AAD a lámalo dešifrování jinde."""
    if isinstance(context, SignatureContext):
        data = context._asdict()
    elif isinstance(context, Mapping):
        data = dict(context)
    else:
        raise InvalidContext("Kontext musí být SignatureContext nebo dict")
    if set(data) != set(FIELDS):
        raise InvalidContext("Kontext musí mít právě klíče " + ", ".join(FIELDS))
    out = {}
    for k in FIELDS:
        v = data[k]
        if not isinstance(v, str) or not v:
            raise InvalidContext(f"Pole {k} musí být neprázdný řetězec")
        out[k] = v
    return out


def canonical(context) -> bytes:
    """Jednoznačné bajty kontextu (třídění klíčů, bez mezer, UTF-8); stejné pro šifrování i dešifrování."""
    return json.dumps(normalize(context), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
