"""Regiony dokumentu: `GET /cases/{c}/regions` a `GET /cases/{c}/documents/{d}/regions` (regions_api, směruje app).
Spuštění: python3 -m pytest -q  (moto)."""
import json

import pytest
from moto import mock_aws

import app
import fixtures
import regions_api

KEY = "fake-test-key-123"


def region(rid, text, label, party=None, refers_to=None, page=1, kind="paragraph"):
    r = {"region_id": rid, "page": page, "order": int(rid.split("-r")[1]), "kind": kind, "text": text,
         "bbox": [0.1, 0.2, 0.9, 0.25], "lines": [{"bbox": [0.1, 0.2, 0.9, 0.25], "start": 0, "end": len(text)}],
         "label": label, "label_source": "llm", "summary": f"Shrnutí {rid}", "section": None, "source": "text_layer"}
    if party:
        r["party"] = party
    if refers_to is not None:
        r["refers_to"] = refers_to
    return r


CONTRACT = [
    region("p1-r01", "SMLOUVA O ÚVĚRU Č. 861005/26", "hlavicka", kind="heading"),
    region("p1-r02", "Dodavatel | Valdorin Stroje s.r.o.", "smluvni_strana", "supplier", kind="table_row"),
    region("p2-r03", "Před čerpáním musí být doložena faktura, potvrzená objednávka a předání stroje. " * 2,
           "povinny_podklad", refers_to=["faktura", "objednavka", "predavaci_protokol"], page=2),
]
ORDER = [region("p1-r01", "Dodavatel / prodávající | Valdorin Stroje Group s.r.o.", "smluvni_strana", "supplier",
                kind="table_row"),
         region("p1-r02", "Objednatel / kupující | Zervanta Stavby a.s.", "smluvni_strana", "buyer", kind="table_row")]


@pytest.fixture
def env():
    with mock_aws():
        api, index, clients = fixtures.build(KEY)
        case = next(c for c in index["cases"] if c["client"] == "Stavby Fišer a.s.")
        done = [d["document_id"] for d in case["documents"] if d["processing_status"] == "completed"]
        yield api, clients, case["case_id"], done


def put_regions(clients, cid, did, regions, key=None, raw=None):
    key = key or f"cases/{cid}/analysis/{did}/regions.json"
    body = raw if raw is not None else json.dumps({"case_id": cid, "document_id": did, "version": 1,
                                                    "pages": [{"page": 1, "source": "text_layer"}],
                                                    "regions": regions}).encode()
    clients.s3.put_object(Bucket=clients.cfg.bucket, Key=key, Body=body)
    clients.ddb.update_item(TableName=clients.cfg.analysis_table,
                            Key={"case_id": {"S": cid}, "document_id": {"S": did}},
                            UpdateExpression="SET regions_s3_key = :k", ExpressionAttributeValues={":k": {"S": key}})


def call(api, path, query=None, key=KEY, method="GET"):
    return regions_api.handle(method, path, query or {}, {"X-Api-Key": key} if key else {}, api=api)


def test_document_regions_full_with_geometry(env):
    api, clients, cid, (did, *_) = env
    put_regions(clients, cid, did, CONTRACT)
    status, body = call(api, f"/cases/{cid}/documents/{did}/regions")
    assert status == 200 and body["status"] == "completed" and body["title"]
    assert [r["region_id"] for r in body["regions"]] == ["p1-r01", "p1-r02", "p2-r03"]
    supplier = body["regions"][1]
    assert supplier["party"] == "supplier" and supplier["text"] == "Dodavatel | Valdorin Stroje s.r.o."
    assert supplier["bbox"] == [0.1, 0.2, 0.9, 0.25] and supplier["lines"][0]["end"] == len(supplier["text"])
    assert "label_source" not in supplier and "order" not in supplier  # jen veřejná pole
    assert body["pages"] == [{"page": 1, "source": "text_layer"}]


def test_outline_is_short_and_has_no_text_or_geometry(env):
    api, clients, cid, (did, *_) = env
    put_regions(clients, cid, did, CONTRACT)
    _, body = call(api, f"/cases/{cid}/documents/{did}/regions", {"outline": "true"})
    podklad = body["regions"][2]
    assert set(podklad) == {"region_id", "page", "kind", "label", "refers_to", "summary", "excerpt"}
    assert podklad["excerpt"].endswith("…") and len(podklad["excerpt"]) == regions_api.EXCERPT + 1


def test_selected_ids_without_geometry_report_missing(env):
    api, clients, cid, (did, *_) = env
    put_regions(clients, cid, did, CONTRACT)
    _, body = call(api, f"/cases/{cid}/documents/{did}/regions", {"ids": "p2-r03,p9-r99", "include_geometry": "false"})
    assert [r["region_id"] for r in body["regions"]] == ["p2-r03"]
    assert "bbox" not in body["regions"][0] and body["regions"][0]["text"].startswith("Před čerpáním")
    assert body["missing_ids"] == ["p9-r99"]


@pytest.mark.parametrize("query, expected", [
    ({"label": "povinny_podklad"}, ["p2-r03"]),
    ({"label": "hlavicka,smluvni_strana"}, ["p1-r01", "p1-r02"]),
    ({"party": "supplier"}, ["p1-r02"]),
    ({"page": "2"}, ["p2-r03"]),
    ({"q": "VALDORIN stroje"}, ["p1-r02"]),
    ({"q": "pred cerpanim"}, ["p2-r03"]),  # bez diakritiky a velikosti písmen
    ({"kind": "table_row", "party": "buyer"}, []),
])
def test_document_filters(env, query, expected):
    api, clients, cid, (did, *_) = env
    put_regions(clients, cid, did, CONTRACT)
    _, body = call(api, f"/cases/{cid}/documents/{did}/regions", query)
    assert [r["region_id"] for r in body["regions"]] == expected


def test_not_run_failed_and_unknown(env):
    api, clients, cid, (did, other, *_) = env
    status, body = call(api, f"/cases/{cid}/documents/{did}/regions")
    assert status == 200 and body["status"] == "not_run" and body["regions"] == []
    put_regions(clients, cid, other, None, raw=b"{not json")
    assert call(api, f"/cases/{cid}/documents/{other}/regions")[1]["status"] == "failed"
    assert call(api, f"/cases/{cid}/documents/neexistuje/regions")[0] == 404
    assert call(api, f"/cases/{cid}/documents/{did}/regions", {"page": "0"})[0] == 400
    assert call(api, f"/cases/{cid}/documents/{did}/regions", {"outline": "ano"})[0] == 400


def test_case_regions_across_documents(env):
    api, clients, cid, (contract, order, *rest) = env
    put_regions(clients, cid, contract, CONTRACT)
    put_regions(clients, cid, order, ORDER)
    status, body = call(api, f"/cases/{cid}/regions", {"label": "smluvni_strana", "party": "supplier"})
    assert status == 200
    got = [(r["document_id"], r["region_id"], r["text"]) for r in body["regions"]]
    assert sorted(got) == sorted([(contract, "p1-r02", "Dodavatel | Valdorin Stroje s.r.o."),
                                  (order, "p1-r01", "Dodavatel / prodávající | Valdorin Stroje Group s.r.o.")])
    assert all(r["title"] and "bbox" not in r for r in body["regions"])  # bez geometrie, pokud se nežádá
    # dokumenty bez regions.json jsou vyjmenované: prázdný výsledek u nich neznamená, že tam nic není
    assert {d["document_id"] for d in body["documents_without_regions"]} >= set(rest)
    _, with_geometry = call(api, f"/cases/{cid}/regions", {"party": "supplier", "include_geometry": "true"})
    assert all(r["bbox"] for r in with_geometry["regions"])


def test_case_regions_need_a_filter_and_a_known_case(env):
    api, clients, cid, _ = env
    assert call(api, f"/cases/{cid}/regions")[0] == 400
    assert call(api, "/cases/neznamy-pripad/regions", {"label": "hlavicka"})[0] == 404


def test_key_method_and_routing_through_app(env, monkeypatch):
    api, clients, cid, (did, *_) = env
    put_regions(clients, cid, did, CONTRACT)
    assert call(api, f"/cases/{cid}/regions", {"label": "x"}, key=None)[0] == 401
    assert call(api, f"/cases/{cid}/regions", {"label": "x"}, key="bad")[0] == 403
    assert call(api, f"/cases/{cid}/regions", {"label": "x"}, method="POST")[0] == 405
    monkeypatch.setattr(app.core, "_default", api)
    event = {"version": "2.0", "rawPath": f"/v1/cases/{cid}/documents/{did}/regions",
             "requestContext": {"http": {"method": "GET"}}, "headers": {"x-api-key": KEY},
             "queryStringParameters": {"label": "povinny_podklad"}}
    response = app.handler(event)
    assert response["statusCode"] == 200 and response["headers"]["Cache-Control"] == "no-store"
    assert [r["region_id"] for r in json.loads(response["body"])["regions"]] == ["p2-r03"]


def _oas(schema):
    """OpenAPI 3.0 -> JSON Schema (nullable), jako v contract_test.py (ten se nedá importovat, spouští kontroly)."""
    if isinstance(schema, dict):
        out = {k: _oas(v) for k, v in schema.items()}
        if out.pop("nullable", False):
            return {"anyOf": [out, {"type": "null"}]}
        return out
    return [_oas(x) for x in schema] if isinstance(schema, list) else schema


def test_responses_match_openapi(env):
    import os

    import yaml
    jsonschema = pytest.importorskip("jsonschema")  # je v requirements-dev.txt, ve venv pipeline ne
    spec = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs",
                                            "openapi-validator-agent.yaml"), encoding="utf-8"))
    components = _oas(spec["components"])

    def valid(name, body):
        jsonschema.validate(body, {"$ref": f"#/components/schemas/{name}", "components": components})

    api, clients, cid, (contract, order, empty, *_) = env
    put_regions(clients, cid, contract, CONTRACT)
    put_regions(clients, cid, order, ORDER)
    doc = f"/cases/{cid}/documents/{contract}/regions"
    for query in ({}, {"outline": "true"}, {"ids": "p1-r02,x", "include_geometry": "false"}):
        valid("DocumentRegions", call(api, doc, query)[1])
    valid("DocumentRegions", call(api, f"/cases/{cid}/documents/{empty}/regions")[1])  # not_run
    valid("CaseRegions", call(api, f"/cases/{cid}/regions", {"party": "supplier"})[1])
    valid("CaseRegions", call(api, f"/cases/{cid}/regions", {"q": "valdorin", "include_geometry": "true"})[1])
    valid("Error", call(api, f"/cases/{cid}/regions")[1])
