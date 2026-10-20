"""Validator Agent API nad skutečnými úložišti (DynamoDB, S3, S3 Vectors).

Čistá funkce `handle(method, path, query, headers) -> (status, body)`; nezná HTTP ani Lambdu.
Kontrakt: be-document-processing/contracts/openapi-validator-agent.yaml, datový kontrakt: be-validator-agent/docs/validator-agent-storage.md.
Závislosti jen boto3 (v Lambda runtime je). API klíč se nikdy nevypisuje ani neloguje.
"""
import base64
import binascii
import hashlib
import hmac
import json
import logging
import math
import os
import re
import time
from decimal import Decimal
from urllib.parse import quote, unquote

log = logging.getLogger("wonderfulkb.agent_api")
audit_log = logging.getLogger("wonderfulkb.agent_api.audit")
audit_log.setLevel(logging.INFO)  # Lambda má kořenový logger na WARNING; auditní řádek musí projít vždy

REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-central-1"))
BASE = "/v1"
ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
READY = ("completed", "partial")
STATUSES = ("awaiting_upload", "queued", "processing", "completed", "partial", "failed")
CROP_TTL = 300
ORIGINAL_TTL = 60  # odkaz na čitelný originál: jen na otevření, každé vydání je v auditu
GET_BATCH = 100  # limit S3 Vectors GetVectors na počet klíčů
MAX_CROP_BLOB = 10 * 1024 * 1024


class ApiError(Exception):
    def __init__(self, status, msg, extra=None):
        super().__init__(msg)
        self.status, self.msg, self.extra = status, msg, extra or {}


class Binary:
    """Odpověď, která není JSON (odkrytý výřez). Adaptéry ji pošlou jako tělo s danou hlavičkou Content-Type."""

    def __init__(self, data, content_type="image/png"):
        self.data, self.content_type = data, content_type
        self.headers = {"Cache-Control": "no-store", "Pragma": "no-cache", "Content-Disposition": "inline",
                        "X-Content-Type-Options": "nosniff"}


def _flag(v):
    return str(v or "").strip().lower() in ("1", "true", "yes")


class Config:
    """Konfigurace z prostředí (výchozí hodnoty = skutečné názvy v účtu <ACCOUNT_ID>)."""

    def __init__(self, env=None):
        e = os.environ if env is None else env
        self.analysis_table = e.get("ANALYSIS_TABLE", "wonderfulkb-uw-document-analysis")
        self.cases_table = e.get("CASES_TABLE", "wonderfulkb-uw-cases")  # jen ověření existence case
        self.bucket = e.get("RAW_BUCKET", "wonderfulkb-raw-document-storage")
        self.vector_bucket = e.get("VECTOR_BUCKET", "wonderfulkb-vectors")
        self.text_index = e.get("TEXT_INDEX", "wonderfulkb-text")
        self.image_index = e.get("IMAGE_INDEX", "wonderfulkb-image")
        self.sig_index = e.get("SIGNATURES_INDEX", "wonderfulkb-signatures")
        self.dimension = int(e.get("VECTOR_DIMENSION", "1024"))
        self.secret_id = e.get("API_KEY_SECRET", "wonderfulkb/ingest-api-key")
        # duplicity napříč případy (dedup/): index hashů a tabulka dokumentů (kvůli sha256); prázdný název funkci vypne
        self.hashes_table = e.get("HASHES_TABLE", "wonderfulkb-uw-content-hashes")
        self.documents_table = e.get("DOCUMENTS_TABLE", "wonderfulkb-uw-documents")
        self.api_key = e.get("API_KEY")  # jen lokální vývoj a testy; v AWS se čte ze Secrets Manageru
        # odkrytí podpisu: KMS klíč (alias nebo ARN) a přechodové přepínače, oba ve výchozím stavu vypnuté
        self.kms_key_id = e.get("PRIVACY_KMS_KEY_ID") or "alias/wonderfulkb-signatures"
        self.legacy_plain_crop_url = _flag(e.get("LEGACY_PLAIN_CROP_URL"))  # čitelný odkaz u nezmigrovaných výřezů
        self.crop_url_compat = _flag(e.get("CROP_URL_COMPAT"))  # ponechá klíč `crop_url` (vždy null) pro starší klienty


class Clients:
    """Líné klienty boto3; v testech se dosadí fake."""

    def __init__(self, cfg, ddb=None, s3=None, s3_presign=None, vectors=None, secrets=None, kms=None,
                 key_provider=None):
        self.cfg = cfg
        self._ddb, self._s3, self._presign, self._vec, self._sec = ddb, s3, s3_presign, vectors, secrets
        self._kms, self._provider = kms, key_provider

    @property
    def ddb(self):
        if self._ddb is None:
            import boto3
            self._ddb = boto3.client("dynamodb", region_name=REGION)
        return self._ddb

    @property
    def s3(self):
        if self._s3 is None:
            import boto3
            self._s3 = boto3.client("s3", region_name=REGION)
        return self._s3

    @property
    def s3_presign(self):
        """Regionální endpoint a SigV4: globální endpoint u čerstvého bucketu přesměrovává a podpis se rozbije."""
        if self._presign is None:
            import boto3
            from botocore.config import Config as BotoConfig
            self._presign = boto3.client(
                "s3", region_name=REGION, endpoint_url=f"https://s3.{REGION}.amazonaws.com",
                config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "virtual"}))
        return self._presign

    @property
    def vectors(self):
        if self._vec is None:
            import boto3
            self._vec = boto3.client("s3vectors", region_name=REGION)
        return self._vec

    @property
    def secrets(self):
        if self._sec is None:
            import boto3
            self._sec = boto3.client("secretsmanager", region_name=REGION)
        return self._sec

    @property
    def key_provider(self):
        """Dešifrování datových klíčů výřezů (jen Decrypt). V testech se dosadí LocalKeyProvider."""
        if self._provider is None:
            from crop_reveal import KmsDecryptor
            if self._kms is None:
                import boto3
                self._kms = boto3.client("kms", region_name=REGION)
            self._provider = KmsDecryptor(self._kms, self.cfg.kms_key_id)
        return self._provider


# ---- autentizace ---------------------------------------------------------

class KeyStore:
    """Drží API klíč v paměti procesu (Lambda kontejner). Klíč se nikdy nevypisuje ani neloguje."""

    TTL = 300

    def __init__(self, clients):
        self.c = clients
        self._key, self._at = None, 0.0

    def get(self):
        if self.c.cfg.api_key:
            return self.c.cfg.api_key.encode()
        if self._key is None or time.monotonic() - self._at > self.TTL:
            self._key = self.c.secrets.get_secret_value(SecretId=self.c.cfg.secret_id)["SecretString"].strip().encode()
            self._at = time.monotonic()
        return self._key

    def check(self, presented):
        if not presented:
            return False
        try:
            return hmac.compare_digest(presented.encode(), self.get())
        except Exception:  # noqa: BLE001  (nepřístupný secret = zamítnout, ne prozradit)
            log.error("Načtení API klíče selhalo")
            raise ApiError(500, "Interní chyba služby") from None


# ---- pomocné -------------------------------------------------------------

def _plain(o):
    """DynamoDB deserializace (Decimal, set) -> JSON."""
    if isinstance(o, Decimal):
        return int(o) if o == o.to_integral_value() else float(o)
    if isinstance(o, dict):
        return {k: _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, (set, frozenset)):
        return sorted(_plain(v) for v in o)
    return o


def _item(raw):
    from boto3.dynamodb.types import TypeDeserializer
    d = TypeDeserializer()
    return _plain({k: d.deserialize(v) for k, v in raw.items()})


def _q1(query, name):
    v = query.get(name)
    if isinstance(v, (list, tuple)):
        v = v[-1] if v else None
    return v


def _bool(query, name, default):
    v = _q1(query, name)
    if v is None:
        return default
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    raise ApiError(400, f"Parametr {name} musí být true nebo false")


def _int(query, name, lo, hi):
    v = _q1(query, name)
    if v is None:
        return None
    try:
        n = int(v)
    except ValueError:
        raise ApiError(400, f"{name} musí být celé číslo") from None
    if not lo <= n <= hi:
        raise ApiError(400, f"{name} musí být {lo} až {hi}")
    return n


def _ids(case_id, document_id=None):
    if not ID_RE.match(case_id) or set(case_id) == {"."}:
        raise ApiError(400, "Neplatné case_id")
    if document_id is not None and (not ID_RE.match(document_id) or set(document_id) == {"."}):
        raise ApiError(400, "Neplatné document_id")


def _ok_status(row):
    return row.get("processing_status") in READY


# ---- čtení z úložišť -------------------------------------------------------

class Repo:
    def __init__(self, clients):
        self.c, self.cfg = clients, clients.cfg

    # DynamoDB
    def get_row(self, case_id, document_id):
        r = self.c.ddb.get_item(TableName=self.cfg.analysis_table, ConsistentRead=True,
                                Key={"case_id": {"S": case_id}, "document_id": {"S": document_id}})
        return _item(r["Item"]) if "Item" in r else None

    def query_rows(self, case_id, status, limit, start_after):
        """Vrátí (řádky do `limit`, jsou další?). Filtr se v DynamoDB aplikuje až po Limit, proto smyčka."""
        kw = dict(TableName=self.cfg.analysis_table,
                  KeyConditionExpression="case_id = :c",
                  ExpressionAttributeValues={":c": {"S": case_id}},
                  ProjectionExpression="document_id, title, #l, label_status, processing_status, page_count",
                  ExpressionAttributeNames={"#l": "label"})
        if status:
            kw["FilterExpression"] = "processing_status = :s"
            kw["ExpressionAttributeValues"][":s"] = {"S": status}
        if start_after:
            kw["ExclusiveStartKey"] = {"case_id": {"S": case_id}, "document_id": {"S": start_after}}
        rows = []
        while True:
            r = self.c.ddb.query(**kw)
            rows += [_item(i) for i in r.get("Items", [])]
            if len(rows) > limit:
                return rows[:limit], True
            if "LastEvaluatedKey" not in r:
                return rows, False
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]

    def ingest_rows(self, case_id):
        """Dokumenty nahrané přes ingest (tabulka dokumentů) jako řádky seznamu se stavem "queued"."""
        if not self.cfg.documents_table:
            return []
        kw = dict(TableName=self.cfg.documents_table, KeyConditionExpression="case_id = :c",
                  ExpressionAttributeValues={":c": {"S": case_id}}, ProjectionExpression="document_id, filename")
        rows = []
        while True:
            r = self.c.ddb.query(**kw)
            rows += [{"document_id": i["document_id"], "title": i.get("filename", ""), "processing_status": "queued"}
                     for i in map(_item, r.get("Items", []))]
            if "LastEvaluatedKey" not in r:
                return rows
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]

    def ingest_document(self, case_id, document_id):
        """{s3_key, filename, content_type} z tabulky dokumentů ingestu, nebo None."""
        if not self.cfg.documents_table:
            return None
        r = self.c.ddb.get_item(TableName=self.cfg.documents_table,
                                ProjectionExpression="s3_key, filename, content_type",
                                Key={"case_id": {"S": case_id}, "document_id": {"S": document_id}})
        return _item(r["Item"]) if "Item" in r else None

    def document_sha256(self, case_id, document_id):
        """SHA-256 obsahu z tabulky dokumentů ingestu (jen tento atribut), nebo None."""
        r = self.c.ddb.get_item(TableName=self.cfg.documents_table, ProjectionExpression="sha256",
                                Key={"case_id": {"S": case_id}, "document_id": {"S": document_id}})
        value = r.get("Item", {}).get("sha256", {}).get("S")
        return value.lower() if value else None

    def hash_matches(self, sha256):
        """[{case_id, document_id, label}] z indexu hashů (všechny případy, i vlastní)."""
        kw = dict(TableName=self.cfg.hashes_table, ConsistentRead=True, KeyConditionExpression="sha256 = :h",
                  ExpressionAttributeValues={":h": {"S": sha256}})
        items = []
        while True:
            r = self.c.ddb.query(**kw)
            items += [_item(i) for i in r.get("Items", [])]
            if "LastEvaluatedKey" not in r:
                break
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
        out = []
        for i in items:
            case, doc = i.get("case_id"), i.get("document_id")
            if not (isinstance(case, str) and isinstance(doc, str) and case and doc):
                composite = i.get("case_document")
                if not (isinstance(composite, str) and "#" in composite):
                    continue  # poškozená položka indexu se přeskočí
                case, doc = composite.split("#", 1)
            label = i.get("label")
            out.append({"case_id": case, "document_id": doc, "label": label if isinstance(label, str) and label else None})
        return sorted(out, key=lambda m: (m["case_id"], m["document_id"]))

    def case_exists(self, case_id):
        r = self.c.ddb.query(TableName=self.cfg.analysis_table, Limit=1, Select="COUNT",
                             KeyConditionExpression="case_id = :c", ExpressionAttributeValues={":c": {"S": case_id}})
        if r.get("Count"):
            return True
        if self.cfg.cases_table:
            return "Item" in self.c.ddb.get_item(TableName=self.cfg.cases_table, Key={"case_id": {"S": case_id}})
        return False

    # S3
    def read_object(self, key):
        try:
            return self.c.s3.get_object(Bucket=self.cfg.bucket, Key=key)["Body"].read()
        except self.c.s3.exceptions.NoSuchKey:
            raise ApiError(500, "Výstup zpracování chybí v úložišti") from None

    def object_exists(self, key):
        """Existenci zjišťuje ListObjectsV2 s předponou (s3:ListBucket omezené na cases/*/analysis/*): bez ListBucket
        by chybějící objekt dal AccessDenied, který se nedá rozlišit od skutečného zamítnutí."""
        r = self.c.s3.list_objects_v2(Bucket=self.cfg.bucket, Prefix=key, MaxKeys=1)
        return any(o["Key"] == key for o in r.get("Contents", []))

    def list_keys(self, prefix):
        """Všechny klíče pod předponou (s3:ListBucket je omezené na cases/*/analysis/*); jedno volání na dokument
        místo jednoho dotazu na každý výřez a náhled."""
        keys, token = set(), None
        while True:
            kw = dict(Bucket=self.cfg.bucket, Prefix=prefix)
            if token:
                kw["ContinuationToken"] = token
            r = self.c.s3.list_objects_v2(**kw)
            keys.update(o["Key"] for o in r.get("Contents", []))
            if not r.get("IsTruncated"):
                return keys
            token = r["NextContinuationToken"]

    def read_blob(self, key):
        """Bajty objektu, nebo None, když neexistuje. Příliš velký objekt je chyba, ne odpověď."""
        try:
            r = self.c.s3.get_object(Bucket=self.cfg.bucket, Key=key)
        except self.c.s3.exceptions.NoSuchKey:
            return None
        if r.get("ContentLength", 0) > MAX_CROP_BLOB:
            raise ApiError(500, "Výstup zpracování je neplatný")
        return r["Body"].read()

    def presign(self, key, ttl=CROP_TTL, content_type=None, filename=None):
        params = {"Bucket": self.cfg.bucket, "Key": key}
        if content_type:
            params["ResponseContentType"] = content_type
        if filename:
            params["ResponseContentDisposition"] = "inline; filename*=UTF-8''" + quote(filename, safe="")
        return self.c.s3_presign.generate_presigned_url("get_object", Params=params, ExpiresIn=ttl)

    # S3 Vectors
    def get_vectors(self, index, keys, data):
        out = []
        for i in range(0, len(keys), GET_BATCH):
            r = self.c.vectors.get_vectors(vectorBucketName=self.cfg.vector_bucket, indexName=index,
                                           keys=keys[i:i + GET_BATCH], returnData=data, returnMetadata=True)
            out += r.get("vectors", [])
        return out

    def document_vectors(self, index, document_id, prefix, page_count, data):
        """Klíče vektorů jsou známé z kontraktu (`<document_id>#t<i>`, `#p<page>`), list_vectors neumí prefix.
        Chybějící klíče get_vectors tiše vynechá; hledá se po blocích, dokud blok není prázdný."""
        found, start = [], (1 if prefix == "p" else 0)
        step = GET_BATCH
        limit = page_count if (prefix == "p" and page_count) else None
        while True:
            n = step if limit is None else min(step, limit - start + 1)
            if n <= 0:
                break
            keys = [f"{document_id}#{prefix}{i}" for i in range(start, start + n)]
            got = self.get_vectors(index, keys, data)
            found += got
            if len(got) < n and limit is None:
                # u textu mohou být indexy 0 i 1 založené; blok bez celé řady znamená konec
                break
            start += n
            if limit is not None and start > limit:
                break
        return found

    def query_neighbors(self, index, vector, own_document_id, top_k):
        r = self.c.vectors.query_vectors(
            vectorBucketName=self.cfg.vector_bucket, indexName=index, topK=top_k,
            queryVector={"float32": vector}, returnMetadata=True, returnDistance=True,
            filter={"$and": [{"verified": {"$eq": True}}, {"document_id": {"$ne": own_document_id}}]})
        return r.get("vectors", [])


def _score(distance):
    """S3 Vectors vrací kosinovou vzdálenost; kontrakt chce podobnost 0 až 1."""
    return round(min(1.0, max(0.0, 1.0 - float(distance))), 4)


def _centroid(vectors):
    if not vectors:
        return None
    dim = len(vectors[0])
    s = [sum(v[i] for v in vectors) for i in range(dim)]
    n = math.sqrt(sum(x * x for x in s)) or 1.0
    return [x / n for x in s]


# ---- operace ---------------------------------------------------------------

class Api:
    def __init__(self, clients=None, cfg=None):
        self.cfg = cfg or (clients.cfg if clients else Config())
        self.c = clients or Clients(self.cfg)
        self.repo = Repo(self.c)
        self.keys = KeyStore(self.c)

    # 0. seznam dokumentů
    def list_documents(self, case_id, query):
        _ids(case_id)
        limit = _int(query, "limit", 1, 100) or 50
        status = _q1(query, "processing_status")
        if status is not None and status not in STATUSES:
            raise ApiError(400, "Neplatný processing_status")
        start = None
        token = _q1(query, "next_token")
        if token:
            try:
                start = json.loads(base64.urlsafe_b64decode(token.encode()))["d"]
                if not isinstance(start, str) or not ID_RE.match(start):
                    raise ValueError
            except (ValueError, KeyError, TypeError, binascii.Error):
                raise ApiError(400, "Neplatný next_token") from None
        # Analýza (zpracované) + ingest (nahrané, pipeline je ještě nezpracovala = "queued").
        merged = {r["document_id"]: r for r in self.repo.ingest_rows(case_id)}
        merged.update({r["document_id"]: r for r in self.repo.query_rows(case_id, None, 10**6, None)[0]})
        if not merged and not self.repo.case_exists(case_id):
            raise ApiError(404, "Case neexistuje")
        rows = [merged[d] for d in sorted(merged) if (start is None or d > start)
                and (status is None or merged[d]["processing_status"] == status)]
        rows, more = rows[:limit], len(rows) > limit
        docs = [{"document_id": r["document_id"], "title": r.get("title", ""), "label": r.get("label"),
                 "label_status": r.get("label_status", "predicted") if r.get("label") else None,
                 "processing_status": r["processing_status"],
                 "page_count": r.get("page_count") if _ok_status(r) else None} for r in rows]
        nxt = base64.urlsafe_b64encode(json.dumps({"d": rows[-1]["document_id"]}).encode()).decode() if more else None
        return {"case_id": case_id, "documents": docs, "next_token": nxt}

    def _row(self, case_id, document_id):
        _ids(case_id, document_id)
        row = self.repo.get_row(case_id, document_id)
        if not row:
            if self.cfg.documents_table and self.repo.document_sha256(case_id, document_id):
                raise ApiError(409, "OCR ještě nedoběhlo", {"processing_status": "queued"})  # jen v ingestu
            raise ApiError(404, "Dokument neexistuje")
        return row

    # 1. dokument
    def get_document(self, case_id, document_id, query):
        row = self._row(case_id, document_id)
        st = row.get("processing_status")
        if st not in READY:
            raise ApiError(409, "OCR ještě nedoběhlo", {"processing_status": st})
        key = row.get("text_s3_key")
        if not key:
            raise ApiError(500, "Výstup zpracování chybí v úložišti")
        label = row.get("label")
        out = {"case_id": case_id, "document_id": document_id, "title": row.get("title", ""),
               "label": label, "label_status": row.get("label_status", "predicted") if label else None,
               "description": row.get("description"),
               "text": self.repo.read_object(key).decode("utf-8"),
               "confidence": None if row.get("confidence") is None else float(row["confidence"]), "page_count": row.get("page_count"),
               "processing_status": st}
        if out["page_count"] is None:
            del out["page_count"]
        if st == "partial":
            out["pages_failed"] = [int(p) for p in sorted(row.get("pages_failed", []))]
        out.update(self._duplicates(case_id, document_id, label))
        return out

    def _duplicates(self, case_id, document_id, label):
        """`duplicate_of` (stejný obsah v jiných případech) a `duplicate_relevant`. Chyba čtení indexu, tabulky
        dokumentů nebo politiky pole jen vynechá: dokument se vrátí i bez nich, nikdy 5xx a bez detailu v odpovědi."""
        if not self.cfg.hashes_table:
            return {}
        try:
            sha = self.repo.document_sha256(case_id, document_id)
            if not sha:
                return {}
            matches = self.repo.hash_matches(sha)
            policy = _duplicate_policy()
        except Exception as error:  # noqa: BLE001 - hash index je doplněk, ne podmínka odpovědi
            log.warning("Duplicity nejdou zjistit: %s", type(error).__name__)
            return {}
        others = [m for m in matches if m["case_id"] != case_id]
        cases = {m["case_id"] for m in matches} | {case_id}
        relevant = (bool(others) and policy["policies"].get(label or "", policy["default"]) == "flag"
                    and len(cases) < policy["template_threshold"])
        return {"duplicate_of": [{"case_id": m["case_id"], "document_id": m["document_id"], "label": m["label"]}
                                 for m in others],
                "duplicate_relevant": relevant}

    # 2. vektory
    def get_vectors(self, case_id, document_id, query):
        row = self._row(case_id, document_id)
        include = _q1(query, "include")
        if include not in (None, "text", "image"):
            raise ApiError(400, "include musí být text nebo image")
        values = _bool(query, "include_values", True)
        n = _int(query, "similar_to_verified", 1, 20)
        out = {"case_id": case_id, "document_id": document_id, "text_vectors": [], "image_vectors": []}
        if not _ok_status(row):
            if n:
                out["neighbors"] = []
            return out
        cfg, repo = self.cfg, self.repo
        text = []
        if include != "image":
            text = repo.document_vectors(cfg.text_index, document_id, "t", None, bool(values or n))
        image = []
        if include != "text":
            image = repo.document_vectors(cfg.image_index, document_id, "p", row.get("page_count"), values)
        text.sort(key=lambda v: _chunk_no(v["key"]))
        image.sort(key=lambda v: _page_no(v))
        if include != "image":
            out["text_vectors"] = [self._vec_out(v, "text", values) for v in text]
        if include != "text":
            out["image_vectors"] = [self._vec_out(v, "image", values) for v in image]
        if n:
            out["neighbors"] = self._neighbors(document_id, n, include, text, image, row)
        return out

    def _vec_out(self, v, kind, values):
        md = v.get("metadata") or {}
        o = {"model": md.get("model", ""), "model_version": md.get("model_version", ""),
             "dimension": len(v["data"]["float32"]) if v.get("data") else int(md.get("dimension", self.cfg.dimension))}
        if values:
            o["values"] = v["data"]["float32"]
        if kind == "text":
            no = _chunk_no(v["key"])
            o["chunk_id"] = md.get("chunk_id", f"c{no}")
            o["page_from"] = int(md.get("page_from", md.get("page", 1)))
            o["page_to"] = int(md.get("page_to", o["page_from"]))
        else:
            o["page"] = _page_no(v)
        return o

    def _neighbors(self, document_id, n, include, text, image, row):
        """Podobnost se hledá nad textem (kvůli typu dokumentu); s include=image nad obrazem.
        Dotaz = těžiště vektorů dokumentu, výsledky po částech se spojí na dokument (nejlepší část)."""
        if include == "image":
            index, vecs = self.cfg.image_index, image
        elif text:
            index, vecs = self.cfg.text_index, text
        else:
            index, vecs = self.cfg.image_index, image
        if not vecs:
            return []
        data = [v["data"]["float32"] for v in vecs if v.get("data")]
        if not data:  # vektory načtené bez dat (include_values=false a vlastní dotaz) se dočtou
            data = [v["data"]["float32"] for v in self.repo.get_vectors(index, [v["key"] for v in vecs], True)]
        q = _centroid(data)
        best = {}
        for hit in self.repo.query_neighbors(index, q, document_id, 100):
            md = hit.get("metadata") or {}
            did = md.get("document_id") or hit["key"].split("#")[0]
            if did == document_id:
                continue
            sc = _score(hit.get("distance", 1.0))
            if did not in best or sc > best[did]["score"]:
                best[did] = {"document_id": did, "label": md.get("label") or "unknown", "score": sc}
        return sorted(best.values(), key=lambda x: -x["score"])[:n]

    # 3. podpisy
    def get_signatures(self, case_id, document_id, query):
        """`status`: completed = signatures.json existuje a je čitelný; not_run = neexistuje (dokument se podpisy
        nezpracoval, prázdné pole NENÍ nález); failed = existuje, ale nejde přečíst nebo nese chybový stav."""
        row = self._row(case_id, document_id)
        match_client = _bool(query, "match_client", False)
        include_vectors = _bool(query, "include_vectors", True)
        out = {"case_id": case_id, "document_id": document_id, "status": "not_run", "signatures": []}
        if not _ok_status(row):
            return out
        key = self._signatures_key(row, case_id, document_id)
        if not self.repo.object_exists(key):
            return out
        sigs = self._read_signatures(key)
        if sigs is None:
            out["status"] = "failed"
            return out
        out["status"] = "completed"
        base = key.rsplit("/", 1)[0]
        vkeys = {s["signature_id"]: f"{document_id}#s{_sig_no(s, i)}" for i, s in enumerate(sigs)}
        vecs = {}
        if sigs and (match_client or include_vectors):
            vecs = {v["key"]: v for v in self.repo.get_vectors(self.cfg.sig_index, list(vkeys.values()), True)}
        present = self.repo.list_keys(f"{base}/signatures/") if sigs else set()
        res = []
        for s in sigs:
            s = dict(s)
            sid = s["signature_id"]
            s.update(self._crop_fields(s, case_id, document_id, base, present))
            v = vecs.get(vkeys[sid])
            if include_vectors:
                if v and not s.get("vector"):
                    md = v.get("metadata") or {}
                    s["vector"] = {"model": md.get("model", ""), "model_version": md.get("model_version", ""),
                                   "dimension": len(v["data"]["float32"]), "values": v["data"]["float32"]}
            else:
                s.pop("vector", None)
            if match_client:
                s["similar_signatures"] = self._similar(case_id, document_id, v)
            else:
                s.pop("similar_signatures", None)
            res.append(s)
        out["signatures"] = res
        return out

    @staticmethod
    def _signatures_key(row, case_id, document_id):
        # atribut tabulky je jen zkratka; pipeline ho nemusí zapsat, proto konvenční klíč z kontraktu
        return row.get("signatures_s3_key") or f"cases/{case_id}/analysis/{document_id}/signatures.json"

    @staticmethod
    def _crop_ref(s, base, present):
        """(klíč výřezu, je šifrovaný) podle `signatures.json` a podle toho, co leží v S3. Klíč mimo
        `<base>/signatures/` se nepoužije (soubor nesmí odkázat na cizí objekt). Bez `crop_s3_key` je to
        `<sig>.png.enc`, pokud existuje, jinak starý čitelný `<sig>.png`."""
        sid, sigdir = s["signature_id"], f"{base}/signatures/"
        key = s.get("crop_s3_key")
        if isinstance(key, str) and key.startswith(sigdir) and ".." not in key:
            return key, s.get("crop_encrypted") is True or key.endswith(".enc")
        enc = f"{sigdir}{sid}.png.enc"
        if enc in present or s.get("crop_encrypted") is True:
            return enc, True
        return f"{sigdir}{sid}.png", False

    def _crop_fields(self, s, case_id, document_id, base, present):
        """Pole výřezu v odpovědi. Čitelný odkaz se nevrací nikdy, kromě nezmigrovaných výřezů při
        `LEGACY_PLAIN_CROP_URL` (výchozí vypnuto). Interní pole (`crop_s3_key`, `crop_encrypted`, `crop_source`,
        `preview_s3_key`) se z odpovědi odstraní."""
        sid, sigdir = s["signature_id"], f"{base}/signatures/"
        key, encrypted = self._crop_ref(s, base, present)
        pkey = s.get("preview_s3_key")
        pkey = pkey if isinstance(pkey, str) and pkey.startswith(sigdir) and ".." not in pkey else f"{sigdir}{sid}.preview.png"
        for k in ("crop_s3_key", "crop_encrypted", "crop_source", "preview_s3_key", "crop_url"):
            s.pop(k, None)
        out = {"reveal_path": f"/cases/{case_id}/documents/{document_id}/signatures/{sid}/image",
               "crop_available": bool(encrypted and key in present),
               "preview_url": self.repo.presign(pkey) if pkey in present else None}
        if self.cfg.legacy_plain_crop_url or self.cfg.crop_url_compat:
            legacy = not encrypted and key in present and self.cfg.legacy_plain_crop_url
            out["crop_url"] = self.repo.presign(key) if legacy else None
        return out

    def _read_signatures(self, key):
        """Seznam podpisů, nebo None, když soubor nejde přečíst (poškozený JSON, špatný tvar, chybový stav)."""
        try:
            doc = json.loads(self.repo.read_object(key).decode("utf-8"))
        except ApiError:  # objekt zmizel mezi kontrolou a čtením
            raise
        except (ValueError, UnicodeDecodeError):
            log.warning("signatures.json není platný JSON")
            return None
        if not isinstance(doc, dict) or doc.get("status") == "failed" or doc.get("error"):
            return None
        sigs = doc.get("signatures", [])
        if sigs is None:
            sigs = []
        if not isinstance(sigs, list) or not all(isinstance(s, dict) and isinstance(s.get("signature_id"), str)
                                                 for s in sigs):
            return None
        return sigs

    def _similar(self, case_id, document_id, v):
        """Nejbližší podpisy téhož klienta; v indexu je klient reprezentován jeho case (`case_id`)."""
        if not v:
            return []
        r = self.c.vectors.query_vectors(
            vectorBucketName=self.cfg.vector_bucket, indexName=self.cfg.sig_index, topK=3,
            queryVector={"float32": v["data"]["float32"]}, returnMetadata=True, returnDistance=True,
            filter={"$and": [{"case_id": {"$eq": case_id}}, {"document_id": {"$ne": document_id}}]})
        out = []
        for hit in r.get("vectors", []):
            md = hit.get("metadata") or {}
            did = md.get("document_id") or hit["key"].split("#")[0]
            out.append({"signature_id": md.get("signature_id") or f"sig_{int(hit['key'].rsplit('#s', 1)[1]) + 1:02d}",
                        "document_id": did, "score": _score(hit.get("distance", 1.0))})
        return out

    # 3b. odkrytí podpisu
    def reveal_signature_image(self, case_id, document_id, signature_id, query, meta=None):
        """Dešifrovaný výřez podpisu (PNG) pro lidskou kontrolu. Čitelný fallback neexistuje: výřez, který není
        šifrovaný, se nevrací (409). Každé volání s platným API klíčem se zapíše do logu jako jeden JSON řádek."""
        _ids(case_id, document_id)
        if not ID_RE.match(signature_id) or set(signature_id) == {"."}:
            raise ApiError(400, "Neplatné signature_id")
        meta = meta or {}
        outcome = "error"
        try:
            png = self._reveal(case_id, document_id, signature_id)
            outcome = "revealed"
            return Binary(png)
        except _Denied:
            outcome = "denied"
            raise ApiError(500, "Odkrytí výřezu selhalo") from None
        except ApiError as e:
            outcome = {404: "not_found", 409: "not_encrypted"}.get(e.status, "error")
            raise
        finally:
            _audit(meta, case_id, document_id, signature_id, outcome)

    def _reveal(self, case_id, document_id, signature_id):
        from crop_reveal import DecryptionError, PNG_MAGIC, context_dict, decrypt_blob, is_encrypted_blob
        row = self._row(case_id, document_id)
        if not _ok_status(row):
            raise ApiError(404, "Podpis neexistuje")
        skey = self._signatures_key(row, case_id, document_id)
        if not self.repo.object_exists(skey):
            raise ApiError(404, "Podpis neexistuje")
        sigs = self._read_signatures(skey)
        if sigs is None:
            raise ApiError(500, "Výstup zpracování je neplatný")
        s = next((x for x in sigs if x["signature_id"] == signature_id), None)
        if s is None:
            raise ApiError(404, "Podpis neexistuje")
        base = skey.rsplit("/", 1)[0]
        present = self.repo.list_keys(f"{base}/signatures/")
        key, encrypted = self._crop_ref(s, base, present)
        if key not in present:
            raise ApiError(404, "Výřez podpisu neexistuje")
        if not encrypted:
            raise ApiError(409, "Výřez ještě není zašifrovaný, odkrytí není možné")
        # kontext z cesty požadavku; `crop_source` jen u výřezu, který byl zašifrován pod jiným podpisem
        # (přesun, migrace). Klíč objektu musí být pod předponou tohoto dokumentu (hlídá _crop_ref).
        ctx = context_dict(case_id, document_id, signature_id)
        src = s.get("crop_source")
        if src is not None:
            if not isinstance(src, dict) or set(src) != set(ctx):
                raise ApiError(500, "Výstup zpracování je neplatný")
            try:
                ctx = context_dict(**src)
            except DecryptionError:
                raise ApiError(500, "Výstup zpracování je neplatný") from None
        blob = self.repo.read_blob(key)
        if blob is None:
            raise ApiError(404, "Výřez podpisu neexistuje")
        if not is_encrypted_blob(blob):
            raise ApiError(409, "Výřez ještě není zašifrovaný, odkrytí není možné")  # nikdy čitelný fallback
        try:
            png = decrypt_blob(blob, ctx, self.c.key_provider)
        except DecryptionError:
            raise _Denied() from None
        if not png.startswith(PNG_MAGIC):
            raise _Denied()
        return png

    # 4. náhled dokumentu (zamaskované stránky) a odkrytí originálu
    def get_pages(self, case_id, document_id, query):
        """Náhled dokumentu po stránkách, obdoba `preview_url` u podpisů: stránky PNG a PDF jen ze zamaskované kopie
        (podpisy začerněné), bez auditu. Dokument zpracovaný před zavedením redakce nemá `redacted_s3_key` a jeho
        `pages/<n>.png` vznikly z čitelného originálu, proto se nevydají (`preview_url: null`, `redacted: false`).
        Čitelný originál jen přes `reveal_path`."""
        row = self._row(case_id, document_id)
        st = row.get("processing_status")
        if st not in READY:
            raise ApiError(409, "OCR ještě nedoběhlo", {"processing_status": st})
        rkey = row.get("redacted_s3_key")
        redacted = (isinstance(rkey, str) and rkey.startswith(f"cases/{case_id}/redacted/") and ".." not in rkey
                    and rkey.endswith(".pdf"))
        prefix = f"cases/{case_id}/analysis/{document_id}/pages/"
        present = self.repo.list_keys(prefix) if redacted else set()
        numbers = {int(m.group(1)) for k in present for m in [re.match(re.escape(prefix) + r"(\d+)\.png$", k)] if m}
        count = row.get("page_count")
        count = int(count) if count is not None and int(count) > 0 else max(numbers, default=0)
        pages = [{"page": n, "preview_url": self.repo.presign(f"{prefix}{n}.png") if n in numbers else None}
                 for n in range(1, count + 1)]
        original = self._original_key(case_id, document_id)
        return {"case_id": case_id, "document_id": document_id, "page_count": count, "redacted": redacted,
                "preview_pdf_url": self.repo.presign(rkey, content_type="application/pdf")
                if redacted and self.repo.object_exists(rkey) else None,
                "pages": pages,
                "original_available": original is not None,
                "reveal_path": f"/cases/{case_id}/documents/{document_id}/original"}

    def _original_key(self, case_id, document_id):
        """(klíč, název souboru, typ) čitelného originálu, nebo None. Klíč z tabulky ingestu musí ležet pod
        `cases/<case>/` a nesmí mířit do `analysis/` ani `redacted/`; bez řádku ingestu konvenční `original/<doc>.pdf`."""
        ing = self.repo.ingest_document(case_id, document_id) or {}
        key = ing.get("s3_key")
        if not (isinstance(key, str) and key.startswith(f"cases/{case_id}/") and ".." not in key
                and "/analysis/" not in key and "/redacted/" not in key):
            key = f"cases/{case_id}/original/{document_id}.pdf"
        if not self.repo.object_exists(key):
            return None
        ctype = ing.get("content_type") if isinstance(ing.get("content_type"), str) else None
        if not ctype:
            ctype = "application/pdf" if key.lower().endswith(".pdf") else "application/octet-stream"
        name = ing.get("filename") if isinstance(ing.get("filename"), str) and ing.get("filename") else key.rsplit("/", 1)[1]
        return key, name, ctype

    def reveal_document_original(self, case_id, document_id, query, meta=None):
        """Krátký předpodepsaný odkaz (60 s) na čitelný originál. Soubor se nevrací v těle (Lambda má limit 6 MB,
        PDF z ingestu mají až desítky MB). Jde i u dokumentu, který se ještě zpracovává. Každé volání s platným
        klíčem zapíše auditní řádek `document_reveal`."""
        _ids(case_id, document_id)
        meta = meta or {}
        outcome = "error"
        try:
            found = self._original_key(case_id, document_id)
            if found is None:
                raise ApiError(404, "Originál dokumentu neexistuje")
            key, name, ctype = found
            out = {"case_id": case_id, "document_id": document_id, "filename": name, "content_type": ctype,
                   "url": self.repo.presign(key, ttl=ORIGINAL_TTL, content_type=ctype, filename=name),
                   "expires_in": ORIGINAL_TTL, "pages": self._original_pages(case_id, document_id)}
            outcome = "revealed"
            return out
        except ApiError as e:
            outcome = "not_found" if e.status == 404 else "error"
            raise
        finally:
            _audit(meta, case_id, document_id, None, outcome, event="document_reveal")

    def _original_pages(self, case_id, document_id):
        """Readable page renders (original-pages/<doc>/<n>.png, the size of pages/<n>.png, so the evidence boxes fit),
        presigned like the original for 60 s; `url: null` for a page not rendered (yet)."""
        prefix = f"cases/{case_id}/original-pages/{document_id}/"
        numbers = {int(m.group(1)) for k in self.repo.list_keys(prefix)
                   for m in [re.match(re.escape(prefix) + r"(\d+)\.png$", k)] if m}
        # the processed page count wins, so renders left over from an earlier, longer run are never handed out
        row = self.repo.get_row(case_id, document_id) or {}
        count = int(row.get("page_count") or 0) or max(numbers, default=0)
        return [{"page": n, "url": self.repo.presign(f"{prefix}{n}.png", ttl=ORIGINAL_TTL, content_type="image/png")
                 if n in numbers else None} for n in range(1, count + 1)]

    # směrování
    ROUTES = [
        (re.compile(r"^/cases/([^/]+)/documents$"), "list_documents"),
        (re.compile(r"^/cases/([^/]+)/documents/([^/]+)$"), "get_document"),
        (re.compile(r"^/cases/([^/]+)/documents/([^/]+)/vectors$"), "get_vectors"),
        (re.compile(r"^/cases/([^/]+)/documents/([^/]+)/signatures$"), "get_signatures"),
        (re.compile(r"^/cases/([^/]+)/documents/([^/]+)/signatures/([^/]+)/image$"), "reveal_signature_image"),
        (re.compile(r"^/cases/([^/]+)/documents/([^/]+)/pages$"), "get_pages"),
        (re.compile(r"^/cases/([^/]+)/documents/([^/]+)/original$"), "reveal_document_original"),
    ]
    AUDITED = ("reveal_signature_image", "reveal_document_original")


class _Denied(Exception):
    """Dešifrování selhalo (zamítnutí KMS, jiný kontext, poškozený blok). Navenek obecné 500, v auditu `denied`."""


def _caller(meta, api_key):
    """Kdo volal, aniž by se prozradil klíč: `apiKeyId` z API Gateway, jinak otisk (SHA-256, 12 znaků) klíče."""
    if meta.get("api_key_id"):
        return str(meta["api_key_id"])
    if api_key:
        return "fp:" + hashlib.sha256(api_key.encode()).hexdigest()[:12]
    return "unknown"


def _audit(meta, case_id, document_id, signature_id, outcome, event="signature_reveal"):
    """Jeden JSON řádek: kdo, kdy, který podpis nebo dokument, výsledek. Bez obsahu obrázku, odkazu, klíče i datového
    klíče. `document_reveal` (originál dokumentu) pole `signature_id` nemá."""
    rec = {"event": event, "caller": meta.get("caller", "unknown"),
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "case_id": case_id, "document_id": document_id,
           "signature_id": signature_id, "outcome": outcome, "request_id": meta.get("request_id")}
    if signature_id is None:
        del rec["signature_id"]
    audit_log.info(json.dumps(rec, ensure_ascii=False))


def _chunk_no(key):
    m = re.search(r"#t(\d+)$", key)
    return int(m.group(1)) if m else 0


def _page_no(v):
    md = v.get("metadata") or {}
    if "page" in md:
        return int(md["page"])
    m = re.search(r"#p(\d+)$", v["key"])
    return int(m.group(1)) if m else 0


def _sig_no(sig, pos):
    """Číslo `n` z klíče vektoru `<document_id>#s<n>`: embed.write_signature_vectors číslují od 0 v pořadí výřezů,
    signature pipeline od 1 (`sig_01`), tedy n = číslo z `signature_id` − 1, jinak pořadí v souboru."""
    m = re.match(r"^sig_(\d+)$", sig.get("signature_id", ""))
    return int(m.group(1)) - 1 if m and int(m.group(1)) >= 1 else pos


_policy_cache = None


def _duplicate_policy():
    """Politika duplicit podle štítku a práh šablony ze snapshotu `duplicate_policy.json` (vyrábí
    `dedup/policy.py` z classify/taxonomy.yaml; Lambda se balí jen z tohoto adresáře). `DEDUP_TEMPLATE_THRESHOLD`
    práh přepíše."""
    global _policy_cache
    if _policy_cache is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "duplicate_policy.json")
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data.get("policies"), dict) or data.get("default") not in ("flag", "ignore"):
            raise ValueError("duplicate_policy.json má špatný tvar")
        if os.environ.get("DEDUP_TEMPLATE_THRESHOLD"):
            data["template_threshold"] = int(os.environ["DEDUP_TEMPLATE_THRESHOLD"])
        data["template_threshold"] = int(data["template_threshold"])
        _policy_cache = data
    return _policy_cache


_default = None


def _check_key(api, hdr):
    if not hdr.get("x-api-key"):  # jako ingest: chybějící klíč 401, špatný 403
        raise ApiError(401, "Chybí API klíč")
    if not api.keys.check(hdr.get("x-api-key")):
        raise ApiError(403, "Špatný API klíč")


def strip_base(path):
    path = unquote(path)
    return path[len(BASE):] if path.startswith(BASE + "/") else path


def authorize(headers, api=None):
    """Stejná kontrola klíče jako v `handle` pro cesty obsluhované jinde (případy a klienti).
    None = povoleno, jinak (status, body)."""
    global _default
    if api is None:
        if _default is None:
            _default = Api()
        api = _default
    try:
        _check_key(api, {k.lower(): v for k, v in (headers or {}).items()})
        return None
    except ApiError as e:
        return e.status, {"error": e.msg}
    except Exception:  # noqa: BLE001
        log.exception("Neošetřená chyba")
        return 500, {"error": "Interní chyba služby"}


def handle(method, path, query=None, headers=None, api=None, request=None):
    """(status, body). `path` smí mít prefix /v1; `query` je {název: hodnota | [hodnoty]}; `headers` bez ohledu na velikost písmen.
    `body` je dict (JSON) nebo `Binary` (odkrytý výřez). `request`: {request_id, api_key_id} z Lambdy pro audit."""
    global _default
    if api is None:
        if _default is None:
            _default = Api()
        api = _default
    query = query or {}
    hdr = {k.lower(): v for k, v in (headers or {}).items()}
    try:
        path = unquote(path)
        if path.startswith(BASE + "/"):
            path = path[len(BASE):]
        if path == "/healthz":
            return 200, {"status": "ok"}
        _check_key(api, hdr)
        for rx, name in Api.ROUTES:
            m = rx.match(path)
            if m:
                if method.upper() != "GET":
                    raise ApiError(405, "Povolena je jen metoda GET")
                if name in Api.AUDITED:
                    meta = dict(request or {}, caller=_caller(request or {}, hdr.get("x-api-key")))
                    return 200, getattr(api, name)(*m.groups(), query, meta=meta)
                return 200, getattr(api, name)(*m.groups(), query)
        raise ApiError(404, "Neznámá cesta")
    except ApiError as e:
        return e.status, {"error": e.msg, **e.extra}
    except Exception:  # noqa: BLE001
        log.exception("Neošetřená chyba")  # traceback bez hlaviček a parametrů
        return 500, {"error": "Interní chyba služby"}


def dumps(body):
    return json.dumps(body, ensure_ascii=False, default=_plain).encode()
