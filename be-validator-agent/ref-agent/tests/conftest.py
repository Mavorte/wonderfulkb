"""Fixtury: mock server (infra/validator-agent-mock) v testu a malý stub API pro vlastní scénáře. Bez AWS, bez LLM."""
import importlib.util
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MOCK_DIR = ROOT.parents[1] / "validator-agent-mock"
KEY = "test-key-9f3a77c1"


def _serve(handler_cls):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture(scope="session")
def mock():
    """Skutečný mock server z repa, na náhodném portu. Vrací objekt s base_url a id případů."""
    sys.path.insert(0, str(MOCK_DIR))
    os.environ["QUIET"] = "1"
    spec = importlib.util.spec_from_file_location("mock_server", MOCK_DIR / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.API_KEY = KEY
    srv = _serve(mod.Handler)
    cases = {c["client"]: cid for cid, c in mod.STORE.cases.items()}

    class M:
        base_url = f"http://127.0.0.1:{srv.server_port}/v1"
        stavby = cases["Stavby Fišer a.s."]
        solom = cases["Solom Rec s.r.o."]
        store = mod.STORE
    yield M
    srv.shutdown()


class Stub:
    """Minimální agent API + ingest API: dokumenty se zadávají v testu."""

    def __init__(self):
        self.cases = {}        # case_id -> {doc_id: spec}
        self.requests = []     # (path, query)
        self.fail = {}         # (path-suffix) -> počet 5xx před úspěchem
        self.ingest = {}       # case_id -> list ingest dokumentů

    def add_case(self, case_id, docs):
        self.cases[case_id] = {d["id"]: d for d in docs}
        return case_id

    def respond(self, path, query, headers):
        self.requests.append((path, query))
        if headers.get("x-api-key") != KEY:
            return 403, {"error": "špatný klíč"}
        m = re.match(r"^/v1/cases/([^/]+)/documents(?:/([^/]+)(?:/(vectors|signatures))?)?$", path)
        im = re.match(r"^/ingest/cases/([^/]+)/documents$", path)
        if im:
            docs = self.ingest.get(im.group(1), [])
            off = int(query.get("next_token", ["0"])[0])
            lim = int(query.get("limit", ["50"])[0])
            nxt = str(off + lim) if off + lim < len(docs) else None
            return 200, {"case_id": im.group(1), "documents": docs[off:off + lim], "next_token": nxt}
        if not m or m.group(1) not in self.cases:
            return 404, {"error": "Case neexistuje"}
        docs, did, kind = self.cases[m.group(1)], m.group(2), m.group(3)
        for suffix, left in list(self.fail.items()):
            if path.endswith(suffix) and left > 0:
                self.fail[suffix] -= 1
                return 503, {"error": "dočasně nedostupné"}
        if did is None:
            return 200, {"case_id": m.group(1), "next_token": None, "documents": [
                {"document_id": d["id"], "title": d["title"], "label": d.get("label"), "label_status": d.get("label_status", "verified"),
                 "processing_status": d.get("status", "completed"), "page_count": d.get("pages", 1)} for d in docs.values()]}
        d = docs.get(did)
        if not d:
            return 404, {"error": "Dokument neexistuje"}
        if kind is None:
            if d.get("status", "completed") not in ("completed", "partial"):
                return 409, {"error": "OCR ještě nedoběhlo", "processing_status": d["status"]}
            out = {"case_id": m.group(1), "document_id": did, "title": d["title"], "label": d.get("label"),
                   "label_status": d.get("label_status", "verified"), "description": d.get("description"), "text": d["text"],
                   "confidence": d.get("confidence", 1.0), "page_count": d.get("pages", 1), "processing_status": d.get("status", "completed")}
            if out["processing_status"] == "partial":
                out["pages_failed"] = d.get("pages_failed", [])
            return 200, out
        if kind == "vectors":
            return 200, {"case_id": m.group(1), "document_id": did, "text_vectors": [], "image_vectors": [],
                         "neighbors": d.get("neighbors", [])}
        sigs = d.get("sigs", [])
        if sigs == "error":
            return 500, {"error": "Textract nedostupný"}
        return 200, {"case_id": m.group(1), "document_id": did, "signatures": sigs}


@pytest.fixture
def stub():
    s = Stub()

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            u = urlparse(self.path)
            status, body = s.respond(u.path, parse_qs(u.query), self.headers)
            raw = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *a):
            pass

    srv = _serve(H)
    s.base_url = f"http://127.0.0.1:{srv.server_port}/v1"
    s.ingest_url = f"http://127.0.0.1:{srv.server_port}/ingest"
    yield s
    srv.shutdown()


def sig(n, role, page=2, suspected=False, evidence=None):
    return {"signature_id": f"sig_{n:02d}", "page": page, "bbox": [0.1, 0.6, 0.4, 0.7], "detector": "textract", "detection_score": 50.0,
            "role": role, "role_source": "nearest_text", "role_evidence": evidence or f"Za {role}",
            "crop_url": f"http://crop.invalid/{n}.png",
            "copy_suspicion": {"level": "suspected" if suspected else "none",
                               "matches": [{"signature_id": "sig_01", "document_id": "x", "score": 1.0}] if suspected else []},
            "similar_signatures": []}


CONTRACT = """SMLOUVA O ÚVĚRU Č. 5555/25
Předběžná kupní cena bez
DPH (dále jen PKC):
Výrobní číslo:
1 000 000,00 CZK
SN1234567
\f
Příjemce financování je povinen před čerpáním úvěru předložit poskytovateli financování následující podklady:
a) kopii kupní smlouvy nebo potvrzené objednávky,
b) smlouvu o zajišťovacím převodu vlastnického práva
 
Dále se strany dohodly na dalších podmínkách.
\fSmlouva č. 5555/25
"""


def clean_case(stub, case_id="CASE-CLEAN", extra=None, contract_text=CONTRACT):
    docs = [
        dict(id="d-contract", title="smlouva.pdf", label="smlouva_o_uveru", text=contract_text, pages=3,
             sigs=[sig(1, "provider", 3), sig(2, "borrower", 3)]),
        dict(id="d-order", title="objednavka.pdf", label="objednavka", text="Objednávka k smlouvě č. 5555/25\nVýr. č.: SN1234567\nCena celkem bez DPH:\n1 000 000,00 CZK\n",
             sigs=[sig(1, "buyer", 1)]),
        dict(id="d-zaj", title="zajisteni.pdf", label="zajistovaci_prevod_vlastnickeho_prava",
             text="Zajišťovaná smlouva o úvěru č.: 5555/25\nVýrobní číslo:\nSN1234567\n", sigs=[sig(1, "borrower", 1), sig(2, "provider", 1)]),
    ] + (extra or [])
    return stub.add_case(case_id, docs)
