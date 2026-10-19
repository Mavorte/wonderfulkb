import boto3

from dedup import backfill, hashindex, lookup

from .conftest import ANALYSIS, DOCUMENTS, HASHES, REGION, SHA_A, SHA_B


def seed():
    ddb = boto3.resource("dynamodb", region_name=REGION)
    documents, analysis = ddb.Table(DOCUMENTS), ddb.Table(ANALYSIS)
    rows = [("c1", "d1", SHA_A), ("c2", "d2", SHA_A), ("c1", "d3", SHA_B), ("c3", "d4", None), ("c3", "d5", "nesmysl")]
    for case, doc, sha in rows:
        item = {"case_id": case, "document_id": doc, "filename": "x.pdf"}
        if sha:
            item["sha256"] = sha
        documents.put_item(Item=item)
    analysis.put_item(Item={"case_id": "c1", "document_id": "d1", "label": "faktura", "processing_status": "completed"})
    analysis.put_item(Item={"case_id": "c1", "document_id": "d3", "processing_status": "queued"})  # bez štítku
    return ddb


def test_dry_run_writes_nothing_and_apply_registers_with_labels(aws):
    ddb = seed()
    out = []
    summary = backfill.run(log=out.append)
    assert summary == {"documents": 5, "without_sha256": 2, "distinct_hashes": 2, "with_label": 1, "hashes_in_more_cases": 1,
                       "applied": False, "registered": 0}
    assert ddb.Table(HASHES).scan()["Items"] == []
    summary = backfill.run(apply=True, log=out.append)
    assert summary["registered"] == 3
    assert lookup(SHA_A) == [{"case_id": "c1", "document_id": "d1", "label": "faktura"},
                             {"case_id": "c2", "document_id": "d2", "label": None}]
    assert lookup(SHA_B) == [{"case_id": "c1", "document_id": "d3", "label": None}]


def test_backfill_is_idempotent_and_does_not_erase_pipeline_labels(aws):
    seed()
    backfill.run(apply=True, log=lambda *_: None)
    hashindex.register(SHA_A, "c2", "d2", "objednavka")  # štítek doplnila pipeline po prvním backfillu
    before = boto3.resource("dynamodb", region_name=REGION).Table(HASHES).scan()["Items"]
    backfill.run(apply=True, log=lambda *_: None)
    after = boto3.resource("dynamodb", region_name=REGION).Table(HASHES).scan()["Items"]
    key = lambda i: i["case_document"]
    assert sorted(before, key=key) == sorted(after, key=key) and len(after) == 3
    assert next(m for m in lookup(SHA_A) if m["case_id"] == "c2")["label"] == "objednavka"


def test_backfill_with_more_than_100_documents(aws):
    ddb = boto3.resource("dynamodb", region_name=REGION)
    for n in range(230):
        ddb.Table(DOCUMENTS).put_item(Item={"case_id": f"c{n}", "document_id": f"d{n}", "sha256": f"{n:064x}"})
        if n % 2:
            ddb.Table(ANALYSIS).put_item(Item={"case_id": f"c{n}", "document_id": f"d{n}", "label": "faktura"})
    summary = backfill.run(apply=True, log=lambda *_: None)
    assert summary["registered"] == 230 and summary["with_label"] == 115
    assert lookup(f"{3:064x}")[0]["label"] == "faktura" and lookup(f"{2:064x}")[0]["label"] is None
