"""Jednotkové testy nad fixturami (moto + fake S3 Vectors). Spuštění: python3 -m pytest -q  (v tomto adresáři)."""
import json
import logging

import pytest
from moto import mock_aws

import core
import fixtures

KEY = "fake-test-key-123"


@pytest.fixture(scope="module")
def env():
    with mock_aws():
        api, index, clients = fixtures.build(KEY)
        yield api, index, clients


def call(api, path, query=None, key=KEY, method="GET"):
    return core.handle(method, "/v1" + path, query or {}, {"X-Api-Key": key} if key else {}, api=api)


def doc(index, client, prefix):
    c = next(c for c in index["cases"] if c["client"] == client)
    d = next(d for d in c["documents"] if d["title"].startswith(prefix))
    return c["case_id"], d["document_id"]


def test_auth_and_healthz(env, caplog):
    api, index, _ = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    assert core.handle("GET", "/healthz", {}, {}, api=api)[0] == 200
    assert core.handle("GET", "/v1/healthz", {}, {}, api=api)[0] == 200  # cesta přes API Gateway se stage
    for k in (None, "", "wrong", KEY + "x", KEY[:-1]):
        st, body = call(api, f"/cases/{cid}/documents/{did}", key=k)
        assert st == 403 and body == {"error": "Chybí nebo je špatný API klíč"}
    caplog.set_level(logging.DEBUG)
    call(api, f"/cases/{cid}/documents/{did}", key="wrong")
    assert KEY not in caplog.text and "wrong" not in caplog.text


def test_key_compared_in_constant_time(env, monkeypatch):
    api, index, _ = env
    seen = []
    real = core.hmac.compare_digest
    monkeypatch.setattr(core.hmac, "compare_digest", lambda a, b: seen.append(1) or real(a, b))
    call(api, "/cases/x/documents", key="wrong")
    assert seen


def test_key_from_secrets_manager_cached_never_in_responses(env, monkeypatch):
    import boto3
    api, index, clients = env
    sec = boto3.client("secretsmanager", region_name="eu-central-1")
    sec.create_secret(Name=clients.cfg.secret_id, SecretString="from-secret-xyz\n")
    calls = []
    orig = sec.get_secret_value
    monkeypatch.setattr(sec, "get_secret_value", lambda **kw: calls.append(1) or orig(**kw))
    monkeypatch.setattr(clients, "_sec", sec)
    monkeypatch.setattr(clients.cfg, "api_key", None)
    monkeypatch.setattr(api.keys, "_key", None)
    cid = index["cases"][0]["case_id"]
    assert call(api, f"/cases/{cid}/documents", key="from-secret-xyz")[0] == 200
    st, body = call(api, f"/cases/{cid}/documents", key="nope")
    assert st == 403 and "from-secret" not in json.dumps(body)
    assert len(calls) == 1  # cache
    sec.delete_secret(SecretId=clients.cfg.secret_id, ForceDeleteWithoutRecovery=True)


def test_secret_failure_is_500_not_leak(env, monkeypatch):
    api, index, clients = env

    class Boom:
        def get_secret_value(self, **kw):
            raise RuntimeError("AccessDenied arn:aws:secretsmanager:...")
    monkeypatch.setattr(clients.cfg, "api_key", None)
    monkeypatch.setattr(api.keys, "_key", None)
    monkeypatch.setattr(clients, "_sec", Boom())
    st, body = call(api, "/cases/x/documents")
    assert st == 500 and body == {"error": "Interní chyba služby"}


def test_unexpected_error_is_generic_500(env, monkeypatch):
    api, index, clients = env

    class Boom:
        def __getattr__(self, n):
            raise RuntimeError("internal detail table wonderfulkb-uw-document-analysis")
    monkeypatch.setattr(clients, "_ddb", Boom())
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    st, body = call(api, f"/cases/{cid}/documents/{did}")
    assert st == 500 and "wonderfulkb" not in json.dumps(body)


def test_method_and_path(env):
    api, index, _ = env
    cid = index["cases"][0]["case_id"]
    assert call(api, f"/cases/{cid}/documents", method="POST")[0] == 405
    assert call(api, "/neco")[0] == 404
    assert call(api, "/cases/../documents/x")[0] in (400, 404)
    assert call(api, "/cases/%2E%2E/documents")[0] == 400


def test_document_and_status_codes(env):
    api, index, _ = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    st, b = call(api, f"/cases/{cid}/documents/{did}")
    assert st == 200 and b["processing_status"] == "completed" and "pages_failed" not in b
    assert b["text"].count("\f") == 3
    cid2, did2 = doc(index, "Stavby Fišer a.s.", "10_")
    st, b = call(api, f"/cases/{cid2}/documents/{did2}")
    assert st == 200 and b["pages_failed"] == [4, 5, 6, 7, 8, 9] and all(isinstance(p, int) for p in b["pages_failed"])
    cid3, did3 = doc(index, "Solom Rec s.r.o.", "11_")
    assert call(api, f"/cases/{cid3}/documents/{did3}") == (409, {"error": "OCR ještě nedoběhlo", "processing_status": "processing"})
    assert call(api, f"/cases/{cid}/documents/neexistuje")[0] == 404


def test_confidence_and_label_nullable(env):
    api, index, _ = env
    cid, did = doc(index, "Solom Rec s.r.o.", "10_")
    st, b = call(api, f"/cases/{cid}/documents/{did}")
    assert st == 200 and b["confidence"] is None
    assert isinstance(call(api, f"/cases/{cid}/documents/{doc(index, 'Solom Rec s.r.o.', '0_')[1]}")[1]["confidence"], float)


def test_list_paging_with_sparse_filter(env):
    api, index, _ = env
    c = next(c for c in index["cases"] if c["client"] == "Stavby Fišer a.s.")
    ids = []
    tok = None
    while True:
        q = {"limit": "1", "processing_status": "completed"}
        if tok:
            q["next_token"] = tok
        st, b = call(api, f"/cases/{c['case_id']}/documents", q)
        assert st == 200
        ids += [d["document_id"] for d in b["documents"]]
        tok = b["next_token"]
        if not tok:
            break
    assert ids == sorted(d["document_id"] for d in c["documents"] if d["processing_status"] == "completed")


def test_list_empty_case_and_unknown_case(env):
    api, index, clients = env
    clients.ddb.put_item(TableName=clients.cfg.cases_table, Item={"case_id": {"S": "empty-case"}})
    assert call(api, "/cases/empty-case/documents") == (200, {"case_id": "empty-case", "documents": [], "next_token": None})
    assert call(api, "/cases/unknown-case/documents")[0] == 404
    cid = index["cases"][0]["case_id"]
    st, b = call(api, f"/cases/{cid}/documents", {"processing_status": "failed"})
    assert st == 200 and b["documents"] == []  # prázdný filtr není 404


def test_vectors_filter_and_exclusion(env):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    clients.vectors.calls.clear()
    st, b = call(api, f"/cases/{cid}/documents/{did}/vectors", {"include_values": "false", "similar_to_verified": "5"})
    assert st == 200 and len(b["neighbors"]) == 5
    assert all("values" not in v for v in b["text_vectors"] + b["image_vectors"])
    assert all(v["dimension"] == 1024 for v in b["text_vectors"] + b["image_vectors"])
    q = [c for c in clients.vectors.calls if c[0] == "query_vectors"]
    assert len(q) == 1 and q[0][1] == "wonderfulkb-text"
    f = json.dumps(q[0][3])
    assert '"verified": {"$eq": true}' in f and did in f
    assert len({n["document_id"] for n in b["neighbors"]}) == 5 and did not in {n["document_id"] for n in b["neighbors"]}
    assert all(0 <= n["score"] <= 1 for n in b["neighbors"])


def test_vectors_include_and_batching(env):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    clients.vectors.calls.clear()
    st, b = call(api, f"/cases/{cid}/documents/{did}/vectors", {"include": "image"})
    assert b["text_vectors"] == [] and [v["page"] for v in b["image_vectors"]] == [1, 2, 3, 4]
    assert all(c[1] == "wonderfulkb-image" for c in clients.vectors.calls)
    st, b = call(api, f"/cases/{cid}/documents/{did}/vectors", {"include": "text"})
    assert b["image_vectors"] == [] and [v["chunk_id"] for v in b["text_vectors"]] == ["c0", "c1"]
    assert (b["text_vectors"][0]["page_from"], b["text_vectors"][0]["page_to"]) == (1, 2)


def test_text_vectors_more_than_one_batch(env):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    base = clients.vectors.idx[("wonderfulkb-vectors", "wonderfulkb-text")][f"{did}#t0"]
    store = clients.vectors.idx[("wonderfulkb-vectors", "wonderfulkb-text")]
    extra = [f"{did}#t{i}" for i in range(2, 130)]
    for k in extra:
        clients.vectors.put("wonderfulkb-vectors", "wonderfulkb-text", k, base[0], base[1])
    try:
        st, b = call(api, f"/cases/{cid}/documents/{did}/vectors", {"include": "text", "include_values": "false"})
        assert len(b["text_vectors"]) == 130  # FakeVectors odmítne víc než 100 klíčů na volání
    finally:
        for k in extra:
            store.pop(k)


def test_vectors_missing_returns_empty_arrays(env, monkeypatch):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    monkeypatch.setattr(clients.vectors, "idx", {})
    st, b = call(api, f"/cases/{cid}/documents/{did}/vectors", {"similar_to_verified": "3"})
    assert st == 200 and b["text_vectors"] == [] and b["image_vectors"] == [] and b["neighbors"] == []


def test_signatures_options(env):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    st, b = call(api, f"/cases/{cid}/documents/{did}/signatures")
    s = b["signatures"][0]
    assert st == 200 and s["vector"]["dimension"] == 1024 and len(s["vector"]["values"]) == 1024
    assert "similar_signatures" not in s and "crop_url" not in s and s["crop_available"] is True
    assert "X-Amz-Signature" in s["preview_url"] and s["reveal_path"].endswith(f"/signatures/{s['signature_id']}/image")
    st, b = call(api, f"/cases/{cid}/documents/{did}/signatures", {"include_vectors": "false", "match_client": "true"})
    s = b["signatures"][0]
    assert "vector" not in s and isinstance(s["similar_signatures"], list)
    assert all(m["document_id"] != did for m in s["similar_signatures"])
    assert not {"crop_s3_key", "crop_encrypted", "crop_source", "preview_s3_key"} & set(s)


def test_signatures_empty_is_valid(env):
    api, index, _ = env
    cid, did = doc(index, "Stavby Fišer a.s.", "99_")
    assert call(api, f"/cases/{cid}/documents/{did}/signatures") == (
        200, {"case_id": cid, "document_id": did, "status": "completed", "signatures": []})


def _with_sig_file(clients, cid, did, body, row_key=True):
    """Dočasně nahradí signatures.json (body=None = smazat) a případně odstraní atribut z řádku."""
    key = f"cases/{cid}/analysis/{did}/signatures.json"
    old = clients.s3.get_object(Bucket=clients.cfg.bucket, Key=key)["Body"].read()
    if body is None:
        clients.s3.delete_object(Bucket=clients.cfg.bucket, Key=key)
    else:
        clients.s3.put_object(Bucket=clients.cfg.bucket, Key=key, Body=body)
    if not row_key:
        clients.ddb.update_item(TableName=clients.cfg.analysis_table, Key={"case_id": {"S": cid}, "document_id": {"S": did}},
                                UpdateExpression="REMOVE signatures_s3_key")
    return key, old


def _restore(clients, cid, did, key, old):
    clients.s3.put_object(Bucket=clients.cfg.bucket, Key=key, Body=old)
    clients.ddb.update_item(TableName=clients.cfg.analysis_table, Key={"case_id": {"S": cid}, "document_id": {"S": did}},
                            UpdateExpression="SET signatures_s3_key = :k", ExpressionAttributeValues={":k": {"S": key}})


def test_signatures_status_matrix(env):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    url = f"/cases/{cid}/documents/{did}/signatures"
    good = json.dumps({"case_id": cid, "document_id": did, "signatures": [
        {"signature_id": "sig_01", "page": 1, "detector": "page_images"}]}).encode()
    cases = [
        (None, "not_run", 0),                                   # soubor neexistuje
        (b'{"case_id": "x", "signatures": []}', "completed", 0),  # existuje a je prázdný: nic nenalezeno
        (good, "completed", 1),                                 # existuje s podpisem
        (b'{"signatures": [', "failed", 0),                      # poškozený JSON
        (b'\xff\xfe', "failed", 0),                             # není UTF-8
        (b'[]', "failed", 0),                                    # špatný tvar
        (b'{"status": "failed", "signatures": []}', "failed", 0),  # chybový stav
        (b'{"error": "textract timeout"}', "failed", 0),
        (b'{"signatures": [{"page": 1}]}', "failed", 0),         # nález bez signature_id
    ]
    for body, status, n in cases:
        key, old = _with_sig_file(clients, cid, did, body)
        try:
            st, b = call(api, url, {"include_vectors": "false"})
            assert (st, b["status"], len(b["signatures"])) == (200, status, n), (body, b)
        finally:
            _restore(clients, cid, did, key, old)


def test_signatures_conventional_key_when_row_attribute_missing(env):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    key, old = _with_sig_file(clients, cid, did, old_or_none(clients, cid, did), row_key=False)
    try:
        st, b = call(api, f"/cases/{cid}/documents/{did}/signatures")
        assert st == 200 and b["status"] == "completed" and len(b["signatures"]) == 2
        assert "X-Amz-Signature" in b["signatures"][0]["preview_url"]
        clients.s3.delete_object(Bucket=clients.cfg.bucket, Key=key)
        st, b = call(api, f"/cases/{cid}/documents/{did}/signatures")
        assert (st, b["status"], b["signatures"]) == (200, "not_run", [])
    finally:
        _restore(clients, cid, did, key, old)


def old_or_none(clients, cid, did):
    return clients.s3.get_object(Bucket=clients.cfg.bucket, Key=f"cases/{cid}/analysis/{did}/signatures.json")["Body"].read()


def test_signatures_not_ready_document_is_not_run(env):
    api, index, _ = env
    cid, did = doc(index, "Solom Rec s.r.o.", "11_")
    st, b = call(api, f"/cases/{cid}/documents/{did}/signatures")
    assert (st, b["status"], b["signatures"]) == (200, "not_run", [])


def test_missing_output_is_500_not_leak(env):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    key = f"cases/{cid}/analysis/{did}/text.txt"
    body = clients.s3.get_object(Bucket=clients.cfg.bucket, Key=key)["Body"].read()
    clients.s3.delete_object(Bucket=clients.cfg.bucket, Key=key)
    try:
        st, b = call(api, f"/cases/{cid}/documents/{did}")
        assert st == 500 and "text.txt" not in json.dumps(b)
    finally:
        clients.s3.put_object(Bucket=clients.cfg.bucket, Key=key, Body=body)


def test_without_cases_table_empty_case_is_404(env, monkeypatch):
    api, index, clients = env
    clients.ddb.put_item(TableName=clients.cfg.cases_table, Item={"case_id": {"S": "empty-case-2"}})
    monkeypatch.setattr(clients.cfg, "cases_table", "")  # CASES_TABLE="" jako v šabloně
    assert call(api, "/cases/empty-case-2/documents")[0] == 404
    cid = index["cases"][0]["case_id"]
    assert call(api, f"/cases/{cid}/documents", {"processing_status": "failed"}) == (
        200, {"case_id": cid, "documents": [], "next_token": None})


# ---- duplicity napříč případy (index hashů) --------------------------------

def _sha(name):
    import hashlib
    return hashlib.sha256(name.encode()).hexdigest()


def _point_at(clients, cid, did, sha, label):
    """Dokument `cid/did` dostane obsah `sha` (v tabulce dokumentů i v indexu) a štítek `label` (v analýze i indexu)."""
    clients.ddb.update_item(TableName=clients.cfg.analysis_table, Key={"case_id": {"S": cid}, "document_id": {"S": did}},
                            UpdateExpression="SET #l = :l", ExpressionAttributeNames={"#l": "label"},
                            ExpressionAttributeValues={":l": {"S": label}})
    fixtures.add_document_hash(clients.ddb, clients.cfg, cid, did, sha, label)


def _other(clients, sha, case_id, label="faktura", document_id=None):
    fixtures.add_document_hash(clients.ddb, clients.cfg, case_id, document_id or f"doc-{case_id}", sha, label)


def _dup(api, cid, did):
    st, b = call(api, f"/cases/{cid}/documents/{did}")
    assert st == 200
    return b.get("duplicate_of"), b.get("duplicate_relevant")


def test_duplicates_none_when_content_is_only_in_own_case(env):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    assert _dup(api, cid, did) == ([], False)


def test_duplicate_individual_document_in_two_cases_is_relevant(env):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    sha = _sha("faktura-ve-dvou-financovanich")
    _point_at(clients, cid, did, sha, "faktura")
    _other(clients, sha, "jine-financovani", "faktura", "d-orig")
    dup, relevant = _dup(api, cid, did)
    assert dup == [{"case_id": "jine-financovani", "document_id": "d-orig", "label": "faktura"}]  # bez vlastního případu
    assert relevant is True


def test_duplicate_template_vop_in_four_cases_is_not_relevant(env):
    api, index, clients = env
    cid, did = doc(index, "Solom Rec s.r.o.", "01_")
    sha = _sha("vop-ve-ctyrech-pripadech")
    _point_at(clients, cid, did, sha, "vop")
    for n in range(3):
        _other(clients, sha, f"vop-case-{n}", "vop")
    dup, relevant = _dup(api, cid, did)
    assert len(dup) == 3 and relevant is False  # duplicita je vidět, ale není relevantní


def test_duplicate_vop_in_two_cases_is_not_relevant_by_policy(env):
    api, index, clients = env
    cid, did = doc(index, "Solom Rec s.r.o.", "01_")
    sha = _sha("vop-ve-dvou")
    _point_at(clients, cid, did, sha, "vop")
    _other(clients, sha, "vop-case-x", "vop")
    assert _dup(api, cid, did)[1] is False


def test_duplicate_individual_document_in_three_cases_hits_template_threshold(env, monkeypatch):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    sha = _sha("faktura-ve-trech")
    _point_at(clients, cid, did, sha, "faktura")
    _other(clients, sha, "tri-a")
    assert _dup(api, cid, did)[1] is True  # dva případy: relevantní
    _other(clients, sha, "tri-b")
    assert _dup(api, cid, did)[1] is False  # tři případy = šablona
    monkeypatch.setenv("DEDUP_TEMPLATE_THRESHOLD", "4")
    monkeypatch.setattr(core, "_policy_cache", None)
    assert _dup(api, cid, did)[1] is True
    monkeypatch.setattr(core, "_policy_cache", None)


def test_duplicate_unknown_label_is_flagged(env):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    sha = _sha("neznamy-stitek")
    _point_at(clients, cid, did, sha, "neexistujici_stitek")
    _other(clients, sha, "jiny-pripad-1", None)
    dup, relevant = _dup(api, cid, did)
    assert relevant is True and dup[0]["label"] is None


def test_duplicate_fields_omitted_when_index_fails(env, monkeypatch, caplog):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    sha = _sha("vypadek-indexu")
    _point_at(clients, cid, did, sha, "faktura")
    monkeypatch.setattr(clients.cfg, "hashes_table", "tabulka-ktera-neexistuje")  # chybí tabulka: ResourceNotFound
    st, b = call(api, f"/cases/{cid}/documents/{did}")
    assert st == 200 and "duplicate_of" not in b and "duplicate_relevant" not in b and b["text"]
    assert "tabulka-ktera-neexistuje" not in caplog.text and sha not in caplog.text
    monkeypatch.setattr(clients.cfg, "hashes_table", "")  # funkce vypnutá
    st, b = call(api, f"/cases/{cid}/documents/{did}")
    assert st == 200 and "duplicate_of" not in b


def test_duplicate_fields_omitted_when_policy_is_unreadable(env, monkeypatch):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    _point_at(clients, cid, did, _sha("bez-politiky"), "faktura")

    def boom():
        raise FileNotFoundError("duplicate_policy.json")
    monkeypatch.setattr(core, "_duplicate_policy", boom)
    st, b = call(api, f"/cases/{cid}/documents/{did}")
    assert st == 200 and "duplicate_of" not in b and b["text"]


def test_duplicate_fields_omitted_for_document_without_known_hash(env):
    api, index, clients = env
    cid2, did2 = doc(index, "Stavby Fišer a.s.", "10_")
    clients.ddb.delete_item(TableName=clients.cfg.documents_table, Key={"case_id": {"S": cid2}, "document_id": {"S": did2}})
    st, b = call(api, f"/cases/{cid2}/documents/{did2}")
    assert st == 200 and "duplicate_of" not in b  # dokument mimo ingest, o hashi nic nevíme


def test_duplicate_corrupted_index_items_are_skipped(env):
    api, index, clients = env
    cid, did = doc(index, "Stavby Fišer a.s.", "0_F")
    sha = _sha("poskozeny-index")
    _point_at(clients, cid, did, sha, "faktura")
    clients.ddb.put_item(TableName=clients.cfg.hashes_table, Item={"sha256": {"S": sha}, "case_document": {"S": "bez-oddelovace"}})
    clients.ddb.put_item(TableName=clients.cfg.hashes_table, Item={"sha256": {"S": sha}, "case_document": {"S": "ok-case#ok-doc"}})
    dup, relevant = _dup(api, cid, did)
    assert dup == [{"case_id": "ok-case", "document_id": "ok-doc", "label": None}] and relevant is True
