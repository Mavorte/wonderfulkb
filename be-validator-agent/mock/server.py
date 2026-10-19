"""Mock Validator Agent API podle be-document-processing/contracts/openapi-validator-agent.yaml.

Bez závislostí (jen stdlib). Spuštění:
    API_KEY=mock-key python3 server.py            # port 8080, PORT=...
Pomocné (mimo spec): GET /healthz, GET /v1/_mock/cases (seznam id), GET /v1/_mock/crops/{doc}/{sig}.png
"""
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import seed

API_KEY = os.environ.get("API_KEY", "mock-key")
BASE = "/v1"
CASE_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
STORE = seed.Store()


class ApiError(Exception):
    def __init__(self, status, msg, extra=None):
        self.status, self.msg, self.extra = status, msg, extra or {}


def parse_bool(qs, name, default):
    if name not in qs:
        return default
    v = qs[name][-1].lower()
    if v in ("true", "false"):
        return v == "true"
    raise ApiError(400, f"Parametr {name} musí být true nebo false")


def lookup(case_id, doc_id):
    if not CASE_RE.match(case_id):
        raise ApiError(400, "Neplatné case_id")
    if case_id not in STORE.cases:
        raise ApiError(404, "Case neexistuje")
    d = STORE.get_doc(case_id, doc_id)
    if not d:
        raise ApiError(404, "Dokument neexistuje")
    return d


def list_case_documents(case_id, qs, host):
    if not CASE_RE.match(case_id):
        raise ApiError(400, "Neplatné case_id")
    if case_id not in STORE.cases:
        raise ApiError(404, "Case neexistuje")
    limit = 50
    if "limit" in qs:
        try:
            limit = int(qs["limit"][-1])
        except ValueError:
            raise ApiError(400, "limit musí být celé číslo")
        if not 1 <= limit <= 100:
            raise ApiError(400, "limit musí být 1 až 100")
    offset = 0
    if "next_token" in qs:
        try:
            offset = int(qs["next_token"][-1])
            if offset < 0:
                raise ValueError
        except ValueError:
            raise ApiError(400, "Neplatný next_token")
    status = qs.get("processing_status", [None])[-1]
    if status not in (None, "awaiting_upload", "queued", "processing", "completed", "partial", "failed"):
        raise ApiError(400, "Neplatný processing_status")
    rows = []
    for did in sorted(STORE.cases[case_id]["docs"]):
        d = STORE.docs[(case_id, did)]
        if status and d["processing_status"] != status:
            continue
        ready = d["processing_status"] in ("completed", "partial")
        rows.append({"document_id": did, "title": d["title"], "label": d["label"],
                     "label_status": d["label_status"], "processing_status": d["processing_status"],
                     "page_count": d["page_count"] if ready else None})
    page = rows[offset:offset + limit]
    nxt = str(offset + limit) if offset + limit < len(rows) else None
    return {"case_id": case_id, "documents": page, "next_token": nxt}


def get_document(case_id, doc_id, qs, host):
    d = lookup(case_id, doc_id)
    if d["processing_status"] not in ("completed", "partial"):
        raise ApiError(409, "OCR ještě nedoběhlo", {"processing_status": d["processing_status"]})
    out = {k: d[k] for k in ("case_id", "document_id", "title", "label", "label_status",
                             "description", "text", "confidence", "page_count", "processing_status")}
    if d["processing_status"] == "partial":
        out["pages_failed"] = d["pages_failed"]
    return out


def get_vectors(case_id, doc_id, qs, host):
    d = lookup(case_id, doc_id)
    include = qs.get("include", [None])[-1]
    if include not in (None, "text", "image"):
        raise ApiError(400, "include musí být text nebo image")
    values = parse_bool(qs, "include_values", True)
    n = None
    if "similar_to_verified" in qs:
        try:
            n = int(qs["similar_to_verified"][-1])
        except ValueError:
            raise ApiError(400, "similar_to_verified musí být celé číslo")
        if not 1 <= n <= 20:
            raise ApiError(400, "similar_to_verified musí být 1 až 20")
    ready = d["processing_status"] in ("completed", "partial")
    out = {"case_id": case_id, "document_id": doc_id,
           "text_vectors": STORE.text_vectors(d, values) if ready and include != "image" else [],
           "image_vectors": STORE.image_vectors(d, values) if ready and include != "text" else []}
    if n:
        out["neighbors"] = STORE.neighbors(d, n)
    return out


def get_signatures(case_id, doc_id, qs, host):
    d = lookup(case_id, doc_id)
    match_client = parse_bool(qs, "match_client", False)
    include_vectors = parse_bool(qs, "include_vectors", True)
    sigs = []
    for item, s in STORE.signatures(d, match_client, include_vectors):
        item["crop_url"] = f"{host}{BASE}/_mock/crops/{doc_id}/{s['signature_id']}.png"
        if not include_vectors:
            item.pop("vector")
        sigs.append(item)
    ready = d["processing_status"] in ("completed", "partial")
    # status: completed = detekce proběhla; not_run = dokument ještě není zpracovaný (prázdné pole NENÍ nález)
    return {"case_id": case_id, "document_id": doc_id, "status": "completed" if ready else "not_run",
            "signatures": sigs}


def list_cases(*_):
    return {"cases": [
        {"case_id": cid, "client": c["client"], "documents": [
            {"document_id": did, "title": STORE.docs[(cid, did)]["title"],
             "label": STORE.docs[(cid, did)]["label"],
             "processing_status": STORE.docs[(cid, did)]["processing_status"],
             "verified": STORE.docs[(cid, did)]["verified"]} for did in c["docs"]]}
        for cid, c in STORE.cases.items()]}


ROUTES = [
    (re.compile(r"^/cases/([^/]+)/documents$"), list_case_documents),
    (re.compile(r"^/cases/([^/]+)/documents/([^/]+)$"), get_document),
    (re.compile(r"^/cases/([^/]+)/documents/([^/]+)/vectors$"), get_vectors),
    (re.compile(r"^/cases/([^/]+)/documents/([^/]+)/signatures$"), get_signatures),
]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, status, body, ctype="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path in ("/healthz", BASE + "/healthz"):
                return self._send(200, {"status": "ok"})
            if not u.path.startswith(BASE + "/"):
                raise ApiError(404, "Neznámá cesta")
            path = u.path[len(BASE):]
            if self.headers.get("x-api-key") != API_KEY:
                raise ApiError(403, "Chybí nebo je špatný API klíč")
            host = f"http://{self.headers.get('Host', 'localhost')}"
            qs = parse_qs(u.query)
            if path == "/_mock/cases":
                return self._send(200, list_cases())
            m = re.match(r"^/_mock/crops/([^/]+)/(sig_\d+)\.png$", path)
            if m:
                s = STORE.sigs.get(f"{m.group(1)}/{m.group(2)}")
                if not s:
                    raise ApiError(404, "Výřez neexistuje")
                return self._send(200, seed.signature_png(s["_seed"]), "image/png")
            for rx, fn in ROUTES:
                m = rx.match(path)
                if m:
                    return self._send(200, fn(*m.groups(), qs, host))
            raise ApiError(404, "Neznámá cesta")
        except ApiError as e:
            self._send(e.status, {"error": e.msg, **e.extra})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": f"Interní chyba: {e}"})

    def log_message(self, fmt, *args):
        if os.environ.get("QUIET") != "1":
            super().log_message(fmt, *args)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"Mock Validator Agent API na :{port}{BASE}, x-api-key = $API_KEY (výchozí 'mock-key')")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
