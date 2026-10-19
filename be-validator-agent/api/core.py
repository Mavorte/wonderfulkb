"""Validator Agent API nad skutečnými úložišti (DynamoDB, S3, S3 Vectors).

Čistá funkce `handle(method, path, query, headers) -> (status, body)`; nezná HTTP ani Lambdu.
Kontrakt: be-document-processing/contracts/openapi-validator-agent.yaml, datový kontrakt: be-validator-agent/docs/validator-agent-storage.md.
Závislosti jen boto3 (v Lambda runtime je). API klíč se nikdy nevypisuje ani neloguje.
"""
import base64
import binascii
import hmac
import json
import logging
import math
import os
import re
import time
from decimal import Decimal
from urllib.parse import unquote

log = logging.getLogger("wonderfulkb.agent_api")

REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-central-1"))
BASE = "/v1"
ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
READY = ("completed", "partial")
STATUSES = ("awaiting_upload", "queued", "processing", "completed", "partial", "failed")
CROP_TTL = 300
GET_BATCH = 100  # limit S3 Vectors GetVectors na počet klíčů


class ApiError(Exception):
    def __init__(self, status, msg, extra=None):
        super().__init__(msg)
        self.status, self.msg, self.extra = status, msg, extra or {}


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
        self.api_key = e.get("API_KEY")  # jen lokální vývoj a testy; v AWS se čte ze Secrets Manageru


class Clients:
    """Líné klienty boto3; v testech se dosadí fake."""

    def __init__(self, cfg, ddb=None, s3=None, s3_presign=None, vectors=None, secrets=None):
        self.cfg = cfg
        self._ddb, self._s3, self._presign, self._vec, self._sec = ddb, s3, s3_presign, vectors, secrets

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

    def crop_url(self, key):
        return self.c.s3_presign.generate_presigned_url(
            "get_object", Params={"Bucket": self.cfg.bucket, "Key": key}, ExpiresIn=CROP_TTL)

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
        rows, more = self.repo.query_rows(case_id, status, limit, start)
        if not rows and not start and not self.repo.case_exists(case_id):
            raise ApiError(404, "Case neexistuje")
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
        return out

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
        # atribut tabulky je jen zkratka; pipeline ho nemusí zapsat, proto konvenční klíč z kontraktu
        key = row.get("signatures_s3_key") or f"cases/{case_id}/analysis/{document_id}/signatures.json"
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
        res = []
        for s in sigs:
            s = dict(s)
            sid = s["signature_id"]
            s["crop_url"] = self.repo.crop_url(s.get("crop_s3_key") or f"{base}/signatures/{sid}.png")
            s.pop("crop_s3_key", None)
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

    # směrování
    ROUTES = [
        (re.compile(r"^/cases/([^/]+)/documents$"), "list_documents"),
        (re.compile(r"^/cases/([^/]+)/documents/([^/]+)$"), "get_document"),
        (re.compile(r"^/cases/([^/]+)/documents/([^/]+)/vectors$"), "get_vectors"),
        (re.compile(r"^/cases/([^/]+)/documents/([^/]+)/signatures$"), "get_signatures"),
    ]


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


_default = None


def handle(method, path, query=None, headers=None, api=None):
    """(status, body). `path` smí mít prefix /v1; `query` je {název: hodnota | [hodnoty]}; `headers` bez ohledu na velikost písmen."""
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
        if not api.keys.check(hdr.get("x-api-key")):
            raise ApiError(403, "Chybí nebo je špatný API klíč")
        for rx, name in Api.ROUTES:
            m = rx.match(path)
            if m:
                if method.upper() != "GET":
                    raise ApiError(405, "Povolena je jen metoda GET")
                return 200, getattr(api, name)(*m.groups(), query)
        raise ApiError(404, "Neznámá cesta")
    except ApiError as e:
        return e.status, {"error": e.msg, **e.extra}
    except Exception:  # noqa: BLE001
        log.exception("Neošetřená chyba")  # traceback bez hlaviček a parametrů
        return 500, {"error": "Interní chyba služby"}


def dumps(body):
    return json.dumps(body, ensure_ascii=False, default=_plain).encode()
