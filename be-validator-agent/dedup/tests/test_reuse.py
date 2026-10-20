"""Znovupoužití hotové analýzy v pipeline: stejný obsah v jiném případu bez nového volání Bedrocku a Textractu."""
import json
from decimal import Decimal

import boto3
import pytest

from dedup import hashindex, lookup, reuse, vectors
from pipeline import Options, Settings, adapters, run_document
from pipeline.tests.conftest import FakeVision, text_pdf

from .conftest import ANALYSIS, BUCKET, DOCUMENTS, REGION, FakeS3Vectors

LINES = ["Faktura c. 2026/0815 odberatel Stavby Fiser s.r.o.", "Cena celkem 1 250 000 Kc bez DPH, variabilni symbol 20260815"]
PDF = text_pdf(LINES, LINES)  # 2 strany


class Models:
    """Počítá volání všeho, co stojí peníze (klasifikace a embedding přes Bedrock, Textract podpisů)."""

    def __init__(self, monkeypatch, s3v):
        self.calls = {"classify": 0, "embed": 0, "signatures": 0}
        self.s3v = s3v
        monkeypatch.setattr(adapters, "classify", self.classify)
        monkeypatch.setattr(adapters, "write_vectors", self.write_vectors)
        monkeypatch.setattr(adapters, "detect_signatures", self.detect_signatures)
        monkeypatch.setattr(vectors, "s3vectors_client", lambda: s3v)

    def classify(self, text, title, page_count):
        self.calls["classify"] += 1
        return {"label": "faktura", "label_status": "predicted", "description": "Faktura za stroj", "confidence": 0.91}

    def write_vectors(self, case_id, document_id, text, page_pngs, label=None):
        self.calls["embed"] += 1
        meta = dict(case_id=case_id, document_id=document_id, verified=False, model="titan", model_version="v2")
        if label:
            meta["label"] = label
        for i in range(3):
            self.s3v.put_vectors("b", "wonderfulkb-text", [{"key": f"{document_id}#t{i}", "data": {"float32": [float(i), 1.0, 0.5, 0.25]},
                                                           "metadata": dict(meta, page=1, chunk_id=f"c{i}", page_from=1, page_to=2)}])
        for n in range(1, len(page_pngs) + 1):
            self.s3v.put_vectors("b", "wonderfulkb-image", [{"key": f"{document_id}#p{n}", "data": {"float32": [0.1, float(n), 0.2, 0.3]},
                                                            "metadata": dict(meta, page=n)}])
        self.s3v.put_vectors("b", "wonderfulkb-signatures", [{"key": f"{document_id}#s0", "data": {"float32": [9.0, 8.0, 7.0, 6.0]},
                                                             "metadata": dict(meta, page=2)}])

    def detect_signatures(self, path, case_id, document_id, s3, bucket):
        self.calls["signatures"] += 1
        return [{"signature_id": "sig_01", "page": 2, "bbox": [0.1, 0.2, 0.3, 0.4], "detector": "textract", "detection_score": 50.0,
                 "role": "buyer", "role_source": "nearest_text", "role_evidence": "Kupujici", "phash": "abcd"}]


@pytest.fixture
def world(aws, monkeypatch):
    s3v = FakeS3Vectors()
    models = Models(monkeypatch, s3v)
    ddb = boto3.resource("dynamodb", region_name=REGION)

    def ingest(case_id, document_id, data=PDF, filename="faktura.pdf"):
        key = f"cases/{case_id}/original/{document_id}.pdf"
        aws.put_object(Bucket=BUCKET, Key=key, Body=data)
        ddb.Table(DOCUMENTS).put_item(Item={"case_id": case_id, "document_id": document_id, "filename": filename, "s3_key": key})

    def options(skip=(), redact=False, **kwargs):
        # redact=False: starší cesta bez maskování podpisů (nepotřebuje KMS ani PyMuPDF); maskovaná cesta má vlastní test
        vision = FakeVision()
        return Options(settings=Settings(skip=frozenset(skip), redact=redact), vision=vision, **kwargs)

    def row(case_id, document_id):
        return ddb.Table(ANALYSIS).get_item(Key={"case_id": case_id, "document_id": document_id}).get("Item")

    class W:
        pass
    w = W()
    w.s3, w.s3v, w.models, w.ingest, w.options, w.row, w.ddb = aws, s3v, models, ingest, options, row, ddb
    return w


def s3_text(w, key):
    return w.s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode()


def process_original(w, case="case-a", doc="doc-a"):
    w.ingest(case, doc)
    r = run_document(case, doc, options=w.options())
    assert r["processing_status"] == "completed" and r["label"] == "faktura"
    return r


def test_same_content_in_second_case_is_reused_without_calling_any_model(world):
    w = world
    original = process_original(w)
    assert w.models.calls == {"classify": 1, "embed": 1, "signatures": 1}
    before = dict(w.models.calls)

    w.ingest("case-b", "doc-b", filename="faktura-b.pdf")
    options = w.options()
    row = run_document("case-b", "doc-b", options=options)

    assert w.models.calls == before            # ani klasifikace, ani embedding, ani Textract
    assert options.vision.calls == 0           # ani vizuální přepis
    assert row["processing_status"] == "completed" and row["reused_from"] == {"case_id": "case-a", "document_id": "doc-a"}
    assert row["title"] == "faktura-b.pdf" and row["page_count"] == 2 and row["pipeline_version"]
    assert (row["label"], row["description"], row["confidence"]) == ("faktura", "Faktura za stroj", Decimal("0.91"))
    assert row["label_status"] == "predicted"
    assert row["text_s3_key"] == "cases/case-b/analysis/doc-b/text.txt"
    assert s3_text(w, row["text_s3_key"]) == s3_text(w, original["text_s3_key"])
    for n in (1, 2):
        assert w.s3.get_object(Bucket=BUCKET, Key=f"cases/case-b/analysis/doc-b/pages/{n}.png")["Body"].read(4) == b"\x89PNG"
    assert w.row("case-b", "doc-b") == row
    run = json.loads(s3_text(w, "cases/case-b/analysis/doc-b/run.json"))
    assert run["reuse"]["status"] == "reused" and run["vision_calls"] == 0

    # vektory pod novými klíči a s metadaty nového dokumentu; zdroj se nezměnil
    assert w.s3v.keys("wonderfulkb-text") == sorted([f"doc-a#t{i}" for i in range(3)] + [f"doc-b#t{i}" for i in range(3)])
    assert w.s3v.keys("wonderfulkb-image") == ["doc-a#p1", "doc-a#p2", "doc-b#p1", "doc-b#p2"]
    assert w.s3v.keys("wonderfulkb-signatures") == ["doc-a#s0", "doc-b#s0"]
    new = w.s3v.store[("wonderfulkb-text", "doc-b#t1")]
    old = w.s3v.store[("wonderfulkb-text", "doc-a#t1")]
    assert new["data"] == old["data"]
    assert new["metadata"] == {**old["metadata"], "case_id": "case-b", "document_id": "doc-b", "verified": False}
    assert w.s3v.store[("wonderfulkb-image", "doc-b#p2")]["metadata"]["case_id"] == "case-b"
    assert old["metadata"]["case_id"] == "case-a" and old["metadata"]["document_id"] == "doc-a"

    # podpisy: nová id, výřez ukazuje na původní objekt, kopie se musí zjistit znovu
    sigs = json.loads(s3_text(w, row["signatures_s3_key"]))
    assert row["signatures_s3_key"] == "cases/case-b/analysis/doc-b/signatures.json"
    assert (sigs["case_id"], sigs["document_id"]) == ("case-b", "doc-b")
    assert sigs["signatures"][0]["crop_s3_key"] == "cases/case-a/analysis/doc-a/signatures/sig_01.png"
    assert sigs["signatures"][0]["copy_suspicion"] == {"level": "not_checked", "matches": []}
    assert sigs["signatures"][0]["phash"] == "abcd" and "crop_url" not in sigs["signatures"][0]

    # oba dokumenty jsou v indexu (druhý se štítkem z pipeline)
    assert {(m["case_id"], m["label"]) for m in lookup(hashes_of(PDF))} == {("case-a", "faktura"), ("case-b", "faktura")}


def hashes_of(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


def test_verified_label_of_original_is_not_inherited(world):
    w = world
    process_original(w)
    w.ddb.Table(ANALYSIS).update_item(Key={"case_id": "case-a", "document_id": "doc-a"},
                                      UpdateExpression="SET label_status = :v", ExpressionAttributeValues={":v": "verified"})
    for key, item in w.s3v.store.items():
        item["metadata"]["verified"] = True
    w.ingest("case-b", "doc-b")
    row = run_document("case-b", "doc-b", options=w.options())
    assert row["label"] == "faktura" and row["label_status"] == "predicted"
    assert all(i["metadata"]["verified"] is False for k, i in w.s3v.store.items() if k[1].startswith("doc-b#"))
    assert w.row("case-a", "doc-a")["label_status"] == "verified"


def test_verified_label_of_the_new_document_is_kept_on_rerun(world):
    w = world
    process_original(w)
    w.ingest("case-b", "doc-b")
    w.ddb.Table(ANALYSIS).put_item(Item={"case_id": "case-b", "document_id": "doc-b", "label": "objednavka", "label_status": "verified",
                                         "description": "Opraveno clovekem", "processing_status": "completed", "page_count": 2})
    row = run_document("case-b", "doc-b", options=w.options())
    assert (row["label"], row["label_status"], row["description"]) == ("objednavka", "verified", "Opraveno clovekem")
    assert w.s3v.store[("wonderfulkb-text", "doc-b#t0")]["metadata"]["label"] == "objednavka"


def test_no_reuse_switch_processes_normally(world):
    w = world
    process_original(w)
    w.ingest("case-b", "doc-b")
    row = run_document("case-b", "doc-b", options=w.options(reuse=False))
    assert w.models.calls == {"classify": 2, "embed": 2, "signatures": 2} and "reused_from" not in row
    assert json.loads(s3_text(w, "cases/case-b/analysis/doc-b/run.json"))["reuse"] == {"status": "disabled"}


def test_environment_switch_disables_reuse(world, monkeypatch):
    monkeypatch.setenv("PIPELINE_NO_REUSE", "1")
    assert Options().reuse is False
    monkeypatch.delenv("PIPELINE_NO_REUSE")
    assert Options().reuse is True


def test_cli_flag_no_reuse(world, monkeypatch):
    from pipeline import __main__ as cli
    seen = {}
    monkeypatch.setattr(cli, "run_document", lambda case, doc, options=None, **kw: seen.setdefault("o", options) and {
        "processing_status": "completed", "document_id": doc, "page_count": 1, "title": "t"})
    cli.main(["run_document", "case-b", "doc-b", "--no-reuse"])
    assert seen["o"].reuse is False
    seen.clear()
    cli.main(["run_document", "case-b", "doc-b"])
    assert seen["o"].reuse is True


@pytest.mark.parametrize("damage", ["partial", "no_row", "failed", "no_text_object", "missing_page_vectors", "no_text_vectors", "bad_signatures"])
def test_missing_or_incomplete_original_falls_back_to_normal_processing(world, damage):
    w = world
    process_original(w)
    table, key = w.ddb.Table(ANALYSIS), {"case_id": "case-a", "document_id": "doc-a"}
    if damage in ("partial", "failed"):
        table.update_item(Key=key, UpdateExpression="SET processing_status = :s", ExpressionAttributeValues={":s": damage})
    elif damage == "no_row":
        table.delete_item(Key=key)
    elif damage == "no_text_object":
        w.s3.delete_object(Bucket=BUCKET, Key="cases/case-a/analysis/doc-a/text.txt")
    elif damage == "missing_page_vectors":
        del w.s3v.store[("wonderfulkb-image", "doc-a#p2")]
    elif damage == "no_text_vectors":
        for i in range(3):
            del w.s3v.store[("wonderfulkb-text", f"doc-a#t{i}")]
    elif damage == "bad_signatures":
        w.s3.put_object(Bucket=BUCKET, Key="cases/case-a/analysis/doc-a/signatures.json", Body=b"{nejde to")
    before = dict(w.models.calls)
    w.ingest("case-b", "doc-b")
    row = run_document("case-b", "doc-b", options=w.options())
    assert row["processing_status"] == "completed" and "reused_from" not in row
    assert w.models.calls == {k: v + 1 for k, v in before.items()}  # zpracováno normálně, ne znovupoužito
    status = json.loads(s3_text(w, "cases/case-b/analysis/doc-b/run.json"))["reuse"]["status"]
    assert status == ("no_source" if damage in ("partial", "no_row", "failed") else "fallback")


def test_original_in_the_same_case_is_not_a_source(world):
    w = world
    process_original(w)
    w.ingest("case-a", "doc-a2")  # jiný document_id, stejný obsah, tentýž případ (nemělo by nastat, ingest to sloučí)
    row = run_document("case-a", "doc-a2", options=w.options())
    assert "reused_from" not in row


def test_missing_index_table_means_normal_processing(world, monkeypatch):
    w = world
    process_original(w)
    w.ingest("case-b", "doc-b")
    monkeypatch.setenv("DEDUP_HASHES_TABLE", "neexistuje")
    row = run_document("case-b", "doc-b", options=w.options())
    assert row["processing_status"] == "completed" and "reused_from" not in row
    assert json.loads(s3_text(w, "cases/case-b/analysis/doc-b/run.json"))["reuse"]["status"] == "index_unavailable"


def test_missing_dedup_module_means_normal_processing(world, monkeypatch):
    w = world
    process_original(w)
    w.ingest("case-b", "doc-b")
    monkeypatch.setattr(adapters, "_load", lambda module, attribute: (_ for _ in ()).throw(adapters.StepUnavailable("no dedup")))
    monkeypatch.setattr(adapters, "classify", w.models.classify)  # _load nahrazen, adaptéry jedou dál přímo
    row = run_document("case-b", "doc-b", options=w.options())
    assert row["processing_status"] == "completed" and "reused_from" not in row


def test_prefers_original_with_verified_label_then_newer(world):
    w = world
    process_original(w, "case-a", "doc-a")
    w.ingest("case-c", "doc-c")
    run_document("case-c", "doc-c", options=w.options(reuse=False))
    w.ddb.Table(ANALYSIS).update_item(Key={"case_id": "case-c", "document_id": "doc-c"},
                                      UpdateExpression="SET label_status = :v", ExpressionAttributeValues={":v": "verified"})
    w.ingest("case-b", "doc-b")
    row = run_document("case-b", "doc-b", options=w.options())
    assert row["reused_from"] == {"case_id": "case-c", "document_id": "doc-c"}


def test_skip_steps_are_respected(world):
    w = world
    process_original(w)
    w.ingest("case-b", "doc-b")
    row = run_document("case-b", "doc-b", options=w.options(skip=("embed", "signatures", "classify")))
    assert row["reused_from"]["case_id"] == "case-a" and "signatures_s3_key" not in row and "label" not in row
    assert not [k for k in w.s3v.keys("wonderfulkb-text") if k.startswith("doc-b")]


def test_existing_signatures_of_the_new_document_are_kept(world):
    w = world
    process_original(w)
    w.ingest("case-b", "doc-b")
    w.s3.put_object(Bucket=BUCKET, Key="cases/case-b/analysis/doc-b/signatures.json", Body=b'{"signatures": []}')
    row = run_document("case-b", "doc-b", options=w.options())
    assert row["signatures_s3_key"] == "cases/case-b/analysis/doc-b/signatures.json"
    assert s3_text(w, row["signatures_s3_key"]) == '{"signatures": []}'


def test_rerun_of_reused_document_is_idempotent(world):
    w = world
    process_original(w)
    w.ingest("case-b", "doc-b")
    first = run_document("case-b", "doc-b", options=w.options())
    keys = sorted(w.s3v.store)
    second = run_document("case-b", "doc-b", options=w.options())
    assert sorted(w.s3v.store) == keys and second["reused_from"] == first["reused_from"]
    assert {k: v for k, v in second.items() if k != "updated_at"} == {k: v for k, v in first.items() if k != "updated_at"}


def test_normal_processing_registers_hash_with_label_and_direct_mode_does_not(world):
    w = world
    r = process_original(w)
    assert lookup(hashes_of(PDF)) == [{"case_id": "case-a", "document_id": "doc-a", "label": "faktura"}]
    from pipeline import Source
    key = "cases/sample/x.pdf"
    w.s3.put_object(Bucket=BUCKET, Key=key, Body=text_pdf(["Jiny dokument, jiny obsah, zcela jiny text 123456"]))
    run_document("pipeline-sample-x", None, source=Source(key), options=w.options())
    import hashlib
    assert lookup(hashlib.sha256(text_pdf(["Jiny dokument, jiny obsah, zcela jiny text 123456"])).hexdigest()) == []
    assert r["processing_status"] == "completed"


def test_direct_mode_can_reuse(world):
    w = world
    process_original(w)
    from pipeline import Source
    w.s3.put_object(Bucket=BUCKET, Key="cases/sample/same.pdf", Body=PDF)
    row = run_document("dataset-case", None, source=Source("cases/sample/same.pdf"), options=w.options())
    assert row["reused_from"]["case_id"] == "case-a"


def test_reuse_functions_read_before_write(world):
    """Neúplný zdroj nesmí nechat v novém dokumentu napůl zapsané vektory ani text."""
    w = world
    process_original(w)
    del w.s3v.store[("wonderfulkb-image", "doc-a#p1")]
    source = w.row("case-a", "doc-a")
    aws = Options(settings=Settings()).get_aws()
    with pytest.raises(reuse.NotReusable):
        reuse.reuse_analysis(aws, source, "case-z", "doc-z", "x.pdf", pipeline_version="1", now=lambda: "t", s3v=w.s3v)
    assert not [k for k in w.s3v.store if k[1].startswith("doc-z")]
    keys = w.s3.list_objects_v2(Bucket=BUCKET, Prefix="cases/case-z/").get("Contents", [])
    assert keys == []


def test_more_than_100_text_chunks_are_all_copied(world):
    w = world
    for i in range(230):
        w.s3v.put_vectors("b", "wonderfulkb-text", [{"key": f"big#t{i}", "data": {"float32": [1.0, 0.0, 0.0, float(i)]},
                                                     "metadata": {"case_id": "c", "document_id": "big", "verified": False}}])
    w.s3v.put_vectors("b", "wonderfulkb-image", [{"key": "big#p1", "data": {"float32": [1.0, 1.0, 1.0, 1.0]},
                                                  "metadata": {"case_id": "c", "document_id": "big", "verified": False}}])
    counts = vectors.copy_document_vectors("big", "c2", "big2", 1, "faktura", s3v=w.s3v)
    assert counts == {"text": 230, "image": 1, "signatures": 0}
    assert len([k for k in w.s3v.keys("wonderfulkb-text") if k.startswith("big2#")]) == 230


def test_masked_pipeline_reuses_only_a_masked_source_and_ties_crops_to_the_source(world):
    """Se zapnutým maskováním (výchozí): zdroj bez `redacted_s3_key` se nepoužije; maskovaný zdroj ano a výřezy
    zůstanou svázané s kontextem zdroje (`crop_source`), nový dokument dostane vlastní maskovanou kopii."""
    w = world
    process_original(w)
    w.ingest("case-b", "doc-b")
    row = run_document_masked_expecting_fallback(w)
    assert row is None

    redacted = "cases/case-a/redacted/doc-a.pdf"
    w.s3.put_object(Bucket=BUCKET, Key=redacted, Body=b"%PDF-masked", Metadata={"original_sha256": hashes_of(PDF)})
    w.ddb.Table(ANALYSIS).update_item(Key={"case_id": "case-a", "document_id": "doc-a"}, UpdateExpression="SET redacted_s3_key = :k",
                                      ExpressionAttributeValues={":k": redacted})
    sigs = json.loads(s3_text(w, "cases/case-a/analysis/doc-a/signatures.json"))
    for sig in sigs["signatures"]:
        sig.update(crop_s3_key="cases/case-a/analysis/doc-a/signatures/sig_01.png.enc", crop_encrypted=True)
    w.s3.put_object(Bucket=BUCKET, Key="cases/case-a/analysis/doc-a/signatures.json", Body=json.dumps(sigs).encode())
    before = dict(w.models.calls)
    row = run_document("case-b", "doc-b", options=w.options(redact=True))
    assert w.models.calls == before and row["reused_from"]["case_id"] == "case-a"
    assert row["redacted_s3_key"] == "cases/case-b/redacted/doc-b.pdf" and row["original_sha256"] == hashes_of(PDF)
    sig = json.loads(s3_text(w, row["signatures_s3_key"]))["signatures"][0]
    assert sig["crop_s3_key"] == "cases/case-a/analysis/doc-a/signatures/sig_01.png.enc"
    assert sig["crop_source"] == {"case_id": "case-a", "document_id": "doc-a", "signature_id": "sig_01"}


def run_document_masked_expecting_fallback(w):
    """Zdroj bez maskované kopie: reuse se přeskočí (zpracování by pak šlo přes maskování; tady se jen ověří důvod)."""
    options = w.options(redact=True)
    report = {}
    from pipeline import run as run_module
    return run_module._try_reuse(options, report, "case-b", "doc-b", "x.pdf", hashes_of(PDF), None) or (
        report["reuse"]["status"] == "source_not_redacted" and None)


def test_regions_are_copied_with_the_new_identity(world):
    w = world
    original = process_original(w)
    source = json.loads(s3_text(w, original["regions_s3_key"]))
    w.ingest("case-b", "doc-b", filename="faktura-b.pdf")
    row = run_document("case-b", "doc-b", options=w.options())
    assert row["reused_from"] == {"case_id": "case-a", "document_id": "doc-a"}
    assert row["regions_s3_key"] == "cases/case-b/analysis/doc-b/regions.json"
    copied = json.loads(s3_text(w, row["regions_s3_key"]))
    assert (copied["case_id"], copied["document_id"], copied["title"]) == ("case-b", "doc-b", "faktura-b.pdf")
    assert copied["regions"] == source["regions"]  # stejný obsah = stejná id a polohy, citace platí i tady
    run = json.loads(s3_text(w, "cases/case-b/analysis/doc-b/run.json"))
    assert run["reuse"]["regions_copied"] is True


def test_broken_source_regions_are_not_copied():
    assert reuse._regions_body(b"not json", "c", "d", "t") is None
    assert reuse._regions_body(b'{"regions": "x"}', "c", "d", "t") is None
    body = json.loads(reuse._regions_body(b'{"case_id": "a", "regions": []}', "c", "d", "t"))
    assert body == {"case_id": "c", "document_id": "d", "title": "t", "regions": []}
