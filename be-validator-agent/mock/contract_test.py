"""Kontrolní test: odpovědi mocku proti schématům v be-document-processing/contracts/openapi-validator-agent.yaml.

    pip install pyyaml jsonschema
    BASE_URL=http://localhost:8080/v1 API_KEY=mock-key python3 contract_test.py
"""
import json
import os
import sys
import urllib.error
import urllib.request

import jsonschema
import yaml

BASE = os.environ.get("BASE_URL", "http://localhost:8080/v1")
KEY = os.environ.get("API_KEY", "mock-key")
SPEC = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "..", "..", "be-document-processing", "contracts", "openapi-validator-agent.yaml")))
fails = 0


def oas(schema):
    """OpenAPI 3.0 -> JSON Schema: nullable a přidání components pro $ref."""
    if isinstance(schema, dict):
        out = {k: oas(v) for k, v in schema.items()}
        if out.get("nullable"):
            out.pop("nullable")
            return {"anyOf": [out, {"type": "null"}]}
        return out
    if isinstance(schema, list):
        return [oas(x) for x in schema]
    return schema


COMPONENTS = oas(SPEC["components"])


def validate(name, body):
    s = {"$ref": f"#/components/schemas/{name}", "components": COMPONENTS}
    jsonschema.validate(body, s)


def call(path, key=KEY):
    req = urllib.request.Request(BASE + path, headers={"x-api-key": key} if key else {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def check(label, cond, detail=""):
    global fails
    print(("OK   " if cond else "FAIL ") + label + (f"  {detail}" if not cond else ""))
    fails += not cond


def expect(path, status, schema=None, key=KEY, label=None):
    st, body = call(path, key)
    ok = st == status
    if ok and schema:
        try:
            validate(schema, body)
        except jsonschema.ValidationError as e:
            ok, st = False, f"{st} schema: {e.message[:200]}"
    check(label or f"{status} {path[:90]}", ok, f"dostal {st}")
    return body


_, idx = call("/_mock/cases")
cases = {c["client"]: c for c in idx["cases"]}
fiser = cases["Stavby Fišer a.s."]
solom = cases["Solom Rec s.r.o."]
by_title = lambda c, t: next(d for d in c["documents"] if d["title"].startswith(t))
smlouva = by_title(fiser, "0_F_Smlouva")
objed = by_title(fiser, "10_")
protokol = by_title(fiser, "11_")
solom_prot = by_title(solom, "11_")
C = fiser["case_id"]

# 0. seznam dokumentů case
b = expect(f"/cases/{C}/documents", 200, "CaseDocumentList")
check("seznam obsahuje všechny dokumenty case a je seřazený",
      len(b["documents"]) == len(fiser["documents"]) and b["next_token"] is None
      and [d["document_id"] for d in b["documents"]] == sorted(d["document_id"] for d in b["documents"]))
b = expect(f"/cases/{C}/documents?limit=2", 200, "CaseDocumentList")
check("stránkování: limit a next_token", len(b["documents"]) == 2 and b["next_token"] is not None)
b2 = expect(f"/cases/{C}/documents?limit=2&next_token={b['next_token']}", 200, "CaseDocumentList")
check("druhá stránka navazuje", b2["documents"][0]["document_id"] != b["documents"][0]["document_id"])
b = expect(f"/cases/{solom['case_id']}/documents?processing_status=processing", 200, "CaseDocumentList")
check("filtr processing_status, page_count null do doběhnutí OCR",
      b["documents"] and all(d["processing_status"] == "processing" and d["page_count"] is None for d in b["documents"]))
for q in ("limit=0", "limit=101", "limit=x", "next_token=abc", "processing_status=hotovo"):
    expect(f"/cases/{C}/documents?{q}", 400, "Error", label=f"400 seznam {q}")
expect("/cases/neexistuje/documents", 404, "Error")
expect(f"/cases/{C}/documents", 403, "Error", key="spatny")

# 1. dokument
b = expect(f"/cases/{C}/documents/{smlouva['document_id']}", 200, "ValidationDocument")
check("text smlouvy má 4 strany oddělené \\f", b["text"].count("\f") == 3 and b["page_count"] == 4)
check("verified dokument", b["label_status"] == "verified" and b["label"] == "smlouva_o_uveru")
b = expect(f"/cases/{C}/documents/{objed['document_id']}", 200, "ValidationDocument")
check("partial vrací pages_failed", b["processing_status"] == "partial" and b["pages_failed"] == [4, 5, 6, 7, 8, 9])
b = expect(f"/cases/{solom['case_id']}/documents/{solom_prot['document_id']}", 409, "NotReady")
check("409 nese processing_status", b["processing_status"] == "processing")
expect(f"/cases/{C}/documents/neexistuje", 404, "Error")
expect(f"/cases/neexistuje/documents/x", 404, "Error")
expect(f"/cases/{C}/documents/{smlouva['document_id']}", 403, "Error", key="spatny")
expect(f"/cases/{C}/documents/{smlouva['document_id']}", 403, "Error", key="")
expect(f"/cases/bad%20id/documents/x", 400, "Error")

# 2. vektory
D = smlouva["document_id"]
b = expect(f"/cases/{C}/documents/{D}/vectors", 200, "DocumentVectors")
check("text i obraz s hodnotami", len(b["text_vectors"]) == 2 and len(b["image_vectors"]) == 4
      and len(b["text_vectors"][0]["values"]) == 1024 and len(b["image_vectors"][0]["values"]) == 1024)
b = expect(f"/cases/{C}/documents/{D}/vectors?include=text&include_values=false&similar_to_verified=5", 200, "DocumentVectors")
check("include=text bez hodnot + neighbors",
      b["image_vectors"] == [] and "values" not in b["text_vectors"][0] and len(b["neighbors"]) == 5)
check("neighbors seřazené sestupně, nejbližší stejného štítku",
      b["neighbors"] == sorted(b["neighbors"], key=lambda n: -n["score"]) and b["neighbors"][0]["label"] == "smlouva_o_uveru"
      and all(n["document_id"] != D for n in b["neighbors"]))
b = expect(f"/cases/{solom['case_id']}/documents/{solom_prot['document_id']}/vectors", 200, "DocumentVectors")
check("nezpracovaný dokument: prázdná pole", b["text_vectors"] == [] and b["image_vectors"] == [])
for q in ("include=audio", "include_values=maybe", "similar_to_verified=0", "similar_to_verified=21"):
    expect(f"/cases/{C}/documents/{D}/vectors?{q}", 400, "Error", label=f"400 {q}")

# 3. podpisy
b = expect(f"/cases/{C}/documents/{D}/signatures", 200, "DocumentSignatures")
check("smlouva: 2 podpisy, copy suspected u příjemce/dodavatele",
      len(b["signatures"]) == 2 and any(s["copy_suspicion"]["level"] == "suspected" for s in b["signatures"]))
b = expect(f"/cases/{C}/documents/{protokol['document_id']}/signatures?match_client=true&include_vectors=false", 200, "DocumentSignatures")
check("kopie podpisu v protokolu + similar_signatures bez vektoru",
      b["signatures"][0]["copy_suspicion"]["matches"] and "vector" not in b["signatures"][0]
      and "similar_signatures" in b["signatures"][0])
with urllib.request.urlopen(urllib.request.Request(b["signatures"][0]["preview_url"], headers={"x-api-key": KEY})) as r:
    check("preview_url vrací PNG", r.read(8) == b"\x89PNG\r\n\x1a\n")
check("podpis má reveal_path a crop_available, crop_url není",
      b["signatures"][0]["reveal_path"].endswith("/image") and b["signatures"][0]["crop_available"] is True
      and "crop_url" not in b["signatures"][0])
b = expect(f"/cases/{C}/documents/{by_title(fiser, '99_')['document_id']}/signatures", 200, "DocumentSignatures")
check("dokument bez podpisů: prázdné pole", b["signatures"] == [])
expect(f"/cases/{C}/documents/{D}/signatures?match_client=x", 400, "Error")

# všechny dokumenty všech případů projdou schématem
n = 0
for c in idx["cases"]:
    for d in c["documents"]:
        for suffix, schema, ok_status in (("", "ValidationDocument", (200, 409)),
                                          ("/vectors?similar_to_verified=3&include_values=false", "DocumentVectors", (200,)),
                                          ("/signatures?match_client=true", "DocumentSignatures", (200,))):
            st, body = call(f"/cases/{c['case_id']}/documents/{d['document_id']}{suffix}")
            if st == 409:
                validate("NotReady", body)
            elif st == 200:
                validate(schema, body)
            if st not in ok_status:
                check(f"{d['title']}{suffix}", False, st)
            n += 1
check(f"všech {n} odpovědí validních podle spec", True)
sys.exit(1 if fails else 0)
