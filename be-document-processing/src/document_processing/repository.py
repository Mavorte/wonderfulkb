"""Small JSON repository with atomic optimistic updates in SQLite and DynamoDB."""
import json
import sqlite3
from copy import deepcopy
from decimal import Decimal
from pathlib import Path


class Conflict(Exception):
    pass


class LocalRepository:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.database = directory / "documents.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS records (pk TEXT, sk TEXT, payload TEXT, PRIMARY KEY(pk, sk))")

    def connect(self):
        return sqlite3.connect(self.database, timeout=15)

    def get(self, pk, sk="META"):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM records WHERE pk=? AND sk=?", (pk, sk)).fetchone()
        return json.loads(row[0]) if row else None

    def create(self, pk, sk, payload):
        try:
            with self.connect() as db:
                db.execute("INSERT INTO records VALUES (?,?,?)", (pk, sk, json.dumps(payload)))
        except sqlite3.IntegrityError as error:
            raise Conflict() from error

    def update(self, pk, sk, mutate):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM records WHERE pk=? AND sk=?", (pk, sk)).fetchone()
            if not row:
                raise KeyError(pk)
            result = mutate(json.loads(row[0]))
            db.execute("UPDATE records SET payload=? WHERE pk=? AND sk=?", (json.dumps(result), pk, sk))
        return result

    def list(self, pk, prefix=""):
        with self.connect() as db:
            rows = db.execute("SELECT sk,payload FROM records WHERE pk=? ORDER BY sk", (pk,)).fetchall()
        return [json.loads(r[1]) for r in rows if r[0].startswith(prefix)]

    def get_case(self, case_id):
        return self.get("CASE#" + case_id)

    def get_client(self, client_id):
        return self.get("CLIENT#" + client_id)


def _to_json(value):
    if isinstance(value, Decimal):
        return int(value) if value == int(value) else float(value)
    raise TypeError(type(value).__name__)


class AwsRepository:
    def __init__(self, settings, resource=None):
        import boto3
        self.resource = resource or boto3.resource("dynamodb", region_name=settings.bedrock_region)
        self.table = self.resource.Table(settings.documents_table)
        self.cases = self.resource.Table(settings.cases_table)
        self.clients = self.resource.Table(settings.clients_table)

    def get(self, pk, sk="META"):
        item = self.table.get_item(Key={"pk": pk, "sk": sk}, ConsistentRead=True).get("Item")
        return json.loads(item["payload"]) if item else None

    def create(self, pk, sk, payload):
        from botocore.exceptions import ClientError
        try:
            self.table.put_item(Item={"pk": pk, "sk": sk, "payload": json.dumps(payload), "revision": 1},
                                ConditionExpression="attribute_not_exists(pk)")
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise Conflict() from error
            raise

    def update(self, pk, sk, mutate):
        from botocore.exceptions import ClientError
        for _ in range(8):
            item = self.table.get_item(Key={"pk": pk, "sk": sk}, ConsistentRead=True).get("Item")
            if not item:
                raise KeyError(pk)
            result = mutate(deepcopy(json.loads(item["payload"])))
            try:
                self.table.put_item(
                    Item={"pk": pk, "sk": sk, "payload": json.dumps(result), "revision": item["revision"] + 1},
                    ConditionExpression="revision = :revision",
                    ExpressionAttributeValues={":revision": item["revision"]},
                )
                return result
            except ClientError as error:
                if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                    raise
        raise Conflict("concurrent updates")

    def list(self, pk, prefix=""):
        from boto3.dynamodb.conditions import Key
        records, cursor = [], None
        while True:
            args = {"KeyConditionExpression": Key("pk").eq(pk) & Key("sk").begins_with(prefix), "ConsistentRead": True}
            if cursor:
                args["ExclusiveStartKey"] = cursor
            response = self.table.query(**args)
            records.extend(json.loads(i["payload"]) for i in response.get("Items", []))
            cursor = response.get("LastEvaluatedKey")
            if not cursor:
                return records

    def get_case(self, case_id):
        item = self.cases.get_item(Key={"case_id": case_id}, ConsistentRead=True).get("Item")
        return json.loads(json.dumps(item, default=_to_json)) if item else None

    def get_client(self, client_id):
        item = self.clients.get_item(Key={"client_id": client_id}, ConsistentRead=True).get("Item")
        return json.loads(json.dumps(item, default=_to_json)) if item else None
