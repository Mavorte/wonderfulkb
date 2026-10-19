"""Index obsahových hashů dokumentů: tabulka `wonderfulkb-uw-content-hashes` (PK `sha256`, SK `case_document`).

Odpovídá na otázku „leží stejný obsah (SHA-256 souboru) ještě v jiném případu?“. Tabulku plní ingest (po zápisu
dokumentu), pipeline (po zpracování, se štítkem) a `backfill.py` (zpětně ze `wonderfulkb-uw-documents`).
Knihovna závisí jen na boto3. Kopie téhož zápisu a čtení je v `infra/ingest/app/content_hashes.py` (ingest se balí
jako samostatný obraz) a v `infra/validator-agent/api/core.py` (Lambda se balí z adresáře `api/`); shodu hlídá test.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

DEFAULT_TABLE = "wonderfulkb-uw-content-hashes"
REGION = "eu-central-1"
SK = "case_document"  # hodnota `<case_id>#<document_id>`
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class HashIndexError(RuntimeError):
    """Index se nepodařilo přečíst nebo zapsat (chybí tabulka, oprávnění, výpadek). Volající rozhodne, co dál."""


def table_name() -> str:
    return os.environ.get("DEDUP_HASHES_TABLE", DEFAULT_TABLE)


def _table(table=None):
    if table is not None and not isinstance(table, str):
        return table  # už hotová Table (testy, opakované použití)
    import boto3
    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or REGION
    return boto3.resource("dynamodb", region_name=region).Table(table or table_name())


def sort_key(case_id: str, document_id: str) -> str:
    return f"{case_id}#{document_id}"


def _check_sha(sha256: str) -> str:
    sha256 = (sha256 or "").strip().lower()
    if not SHA_RE.match(sha256):
        raise ValueError("sha256 musí být 64 hexadecimálních znaků")
    return sha256


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def register(sha256: str, case_id: str, document_id: str, label: str | None = None, *, table=None) -> None:
    """Zapíše dokument do indexu. Idempotentní a bezpečné při souběhu: jediný `UpdateItem`, `registered_at` se
    nastaví jen poprvé, `label` se přepíše jen když je zadaný (ingest štítek nezná, pipeline ho doplní)."""
    sha256 = _check_sha(sha256)
    if not case_id or not document_id or "#" in case_id:
        raise ValueError("case_id a document_id jsou povinné, case_id nesmí obsahovat '#'")
    sets = ["case_id = :c", "document_id = :d", "registered_at = if_not_exists(registered_at, :now)"]
    values = {":c": case_id, ":d": document_id, ":now": now_iso()}
    if label:
        sets.append("#l = :l")
        values[":l"] = label
    kwargs = {"Key": {"sha256": sha256, SK: sort_key(case_id, document_id)},
              "UpdateExpression": "SET " + ", ".join(sets), "ExpressionAttributeValues": values}
    if label:
        kwargs["ExpressionAttributeNames"] = {"#l": "label"}
    try:
        _table(table).update_item(**kwargs)
    except Exception as error:  # noqa: BLE001
        raise HashIndexError(f"zápis do indexu hashů selhal: {type(error).__name__}") from error


def lookup(sha256: str, *, exclude_case_id: str | None = None, table=None) -> list[dict]:
    """Všechny dokumenty se stejným obsahem: `[{case_id, document_id, label}]` (label `None`, když ho index nezná).
    S `exclude_case_id` bez dokumentů téhož případu. Poškozené položky (bez id) se přeskočí."""
    sha256 = _check_sha(sha256)
    from boto3.dynamodb.conditions import Key
    tbl = _table(table)
    items, kwargs = [], {"KeyConditionExpression": Key("sha256").eq(sha256), "ConsistentRead": True}
    try:
        while True:
            page = tbl.query(**kwargs)
            items += page.get("Items", [])
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    except Exception as error:  # noqa: BLE001
        raise HashIndexError(f"čtení indexu hashů selhalo: {type(error).__name__}") from error
    return normalize_items(items, exclude_case_id)


def normalize_items(items, exclude_case_id=None) -> list[dict]:
    out = []
    for item in items:
        case_id, document_id = item.get("case_id"), item.get("document_id")
        if not (isinstance(case_id, str) and isinstance(document_id, str) and case_id and document_id):
            composite = item.get(SK)
            if isinstance(composite, str) and "#" in composite:
                case_id, document_id = composite.split("#", 1)
            else:
                continue
        if exclude_case_id is not None and case_id == exclude_case_id:
            continue
        label = item.get("label")
        out.append({"case_id": case_id, "document_id": document_id, "label": label if isinstance(label, str) and label else None})
    out.sort(key=lambda x: (x["case_id"], x["document_id"]))
    return out
