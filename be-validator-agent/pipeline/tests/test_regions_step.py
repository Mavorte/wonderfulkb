"""Krok `regions`: regiony (odstavce s bbox a štítky) zamaskovaného PDF do analysis/<doc>/regions.json."""
import json

from pipeline import adapters, run_document

from .conftest import BUCKET, text_pdf

LINES = ["Smlouva o uveru c. 861005/26", "Dodavatel: Valdorin Stroje s.r.o.",
         "Pred cerpanim musi byt dolozena faktura a potvrzena objednavka."]


def s3_json(s3, key):
    return json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())


def test_regions_are_written_and_referenced(ingest, make_options, aws_env):
    ingest("c1", "d1", text_pdf(LINES), "smlouva.pdf")
    row = run_document("c1", "d1", options=make_options())
    assert row["regions_s3_key"] == "cases/c1/analysis/d1/regions.json"
    body = s3_json(aws_env, row["regions_s3_key"])
    assert (body["case_id"], body["document_id"], body["title"]) == ("c1", "d1", "smlouva.pdf")
    assert body["pages"][0]["source"] == "text_layer" and body["regions"]
    region = body["regions"][0]
    assert region["region_id"] == "p1-r01" and len(region["bbox"]) == 4 and region["label"]
    assert all(r["label_source"] == "rules" for r in body["regions"])  # regions_llm=False in tests
    steps = s3_json(aws_env, "cases/c1/analysis/d1/run.json")["steps"]
    assert steps["regions"]["status"] == "ok" and steps["regions"]["labels"]["calls"] == 0


def test_regions_get_the_classified_label_and_the_llm_switch(ingest, make_options, monkeypatch):
    seen = {}
    monkeypatch.setattr(adapters, "classify", lambda text, title, n: {"label": "smlouva_o_uveru", "label_status": "predicted",
                                                                       "description": "Smlouva", "confidence": 0.9})

    def regions(pdf_bytes, doc_label=None, use_llm=True):
        seen.update(pdf=bytes(pdf_bytes[:5]), doc_label=doc_label, use_llm=use_llm)
        return {"version": 1, "pages": [], "regions": []}, {"calls": 0}

    monkeypatch.setattr(adapters, "regions", regions)
    ingest("c1", "d1", text_pdf(LINES))
    run_document("c1", "d1", options=make_options(skip=("embed", "signatures")))
    assert seen == {"pdf": b"%PDF-", "doc_label": "smlouva_o_uveru", "use_llm": False}


def test_failing_regions_do_not_change_the_status(ingest, make_options, monkeypatch, aws_env):
    monkeypatch.setattr(adapters, "regions", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    ingest("c1", "d1", text_pdf(LINES))
    row = run_document("c1", "d1", options=make_options())
    assert row["processing_status"] == "completed" and "regions_s3_key" not in row
    steps = s3_json(aws_env, "cases/c1/analysis/d1/run.json")["steps"]
    assert steps["regions"] == {"status": "failed", "error": "RuntimeError: boom"}


def test_skip_keeps_existing_regions(ingest, make_options, aws_env, monkeypatch):
    monkeypatch.setattr(adapters, "regions", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")))
    key = "cases/c1/analysis/d1/regions.json"
    aws_env.put_object(Bucket=BUCKET, Key=key, Body=b'{"regions": []}')
    ingest("c1", "d1", text_pdf(LINES))
    row = run_document("c1", "d1", options=make_options(skip=("classify", "embed", "signatures", "regions")))
    assert row["regions_s3_key"] == key
    assert aws_env.get_object(Bucket=BUCKET, Key=key)["Body"].read() == b'{"regions": []}'


def test_regions_case_only_adds_regions_to_processed_masked_documents(ingest, make_options, aws_env):
    from pipeline import regions_case
    from pipeline.run import analysis_prefix

    from .conftest import analysis_row
    ingest("c1", "d1", text_pdf(LINES), "smlouva.pdf")
    ingest("c1", "d2", text_pdf(LINES), "bez-maskovani.pdf")
    run_document("c1", "d1", options=make_options(skip=("classify", "embed", "signatures", "regions")))
    run_document("c1", "d2", options=make_options(skip=("classify", "embed", "signatures", "regions")))
    # d1 má zamaskovanou kopii (tady jen stejné PDF pod klíčem redacted/), d2 ne
    aws_env.put_object(Bucket=BUCKET, Key="cases/c1/redacted/d1.pdf", Body=text_pdf(LINES))
    import boto3
    table = boto3.resource("dynamodb", region_name="eu-central-1").Table("wonderfulkb-uw-document-analysis")
    table.update_item(Key={"case_id": "c1", "document_id": "d1"}, UpdateExpression="SET redacted_s3_key = :k",
                      ExpressionAttributeValues={":k": "cases/c1/redacted/d1.pdf"})
    before = analysis_row("c1", "d1")

    results = regions_case("c1", make_options())
    assert {r["document_id"]: r["status"] for r in results} == {"d1": "ok", "d2": "not_redacted"}
    after = analysis_row("c1", "d1")
    assert after == {**before, "regions_s3_key": analysis_prefix("c1", "d1") + "regions.json"}  # nic jiného se nezměnilo
    assert "regions_s3_key" not in analysis_row("c1", "d2")
    body = s3_json(aws_env, after["regions_s3_key"])
    assert body["regions"] and body["title"] == "smlouva.pdf"
    run = s3_json(aws_env, analysis_prefix("c1", "d1") + "run.json")
    assert run["steps"]["regions"]["status"] == "ok" and run["steps"]["regions"]["via"] == "regions_case"
