"""Index obsahových hashů (DynamoDB `wonderfulkb-uw-content-hashes`, PK `sha256`, SK `case_document` = `<case_id>#<document_id>`).

Ingest se balí jako samostatný obraz, proto je tu malá kopie knihovny `infra/validator-agent/dedup/hashindex.py`
(stejný zápis a čtení; shodu hlídá test v dedup/tests). Tabulka je volitelná: prázdný `HASHES_TABLE` index vypne.
Chyba indexu nesmí shodit nahrání, volající ji zachytí; do logu patří jen typ chyby, nikdy hash ani id."""
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config

TABLE_NAME = os.environ.get("HASHES_TABLE", "wonderfulkb-uw-content-hashes")
REGION = os.environ.get("AWS_REGION", "eu-central-1")
_table = None


def enabled():
    return bool(TABLE_NAME)


def table():
    """Krátké timeouty: výpadek indexu nemá nahrání zdržet."""
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=REGION, config=Config(
            connect_timeout=2, read_timeout=3, retries={"max_attempts": 2, "mode": "standard"})).Table(TABLE_NAME)
    return _table


def lookup_other_cases(sha256, case_id):
    """[{case_id, document_id}] se stejným obsahem v JINÝCH případech (seřazeno). Při chybě vyvolá výjimku."""
    items, kwargs = [], {"KeyConditionExpression": Key("sha256").eq(sha256), "ConsistentRead": True}
    while True:
        page = table().query(**kwargs)
        items += page.get("Items", [])
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    out = []
    for item in items:
        other_case, other_doc = item.get("case_id"), item.get("document_id")
        if not (isinstance(other_case, str) and isinstance(other_doc, str) and other_case and other_doc):
            composite = item.get("case_document")
            if not (isinstance(composite, str) and "#" in composite):
                continue
            other_case, other_doc = composite.split("#", 1)
        if other_case != case_id:
            out.append({"case_id": other_case, "document_id": other_doc})
    return sorted(out, key=lambda x: (x["case_id"], x["document_id"]))


def register(sha256, case_id, document_id):
    """Idempotentní zápis (`registered_at` se nastaví jen poprvé; štítek doplní až pipeline)."""
    table().update_item(
        Key={"sha256": sha256, "case_document": f"{case_id}#{document_id}"},
        UpdateExpression="SET case_id = :c, document_id = :d, registered_at = if_not_exists(registered_at, :now)",
        ExpressionAttributeValues={":c": case_id, ":d": document_id,
                                   ":now": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
