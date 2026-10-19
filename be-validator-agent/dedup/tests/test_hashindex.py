import threading
from pathlib import Path

import pytest
import yaml

from dedup import HashIndexError, hashindex, lookup, register

from .conftest import HASHES, SHA_A, SHA_B


def test_register_and_lookup_same_content_in_two_cases(aws):
    register(SHA_A, "case-1", "doc-1", "faktura")
    register(SHA_A, "case-2", "doc-2")
    register(SHA_B, "case-1", "doc-3", "vop")
    assert lookup(SHA_A) == [{"case_id": "case-1", "document_id": "doc-1", "label": "faktura"},
                             {"case_id": "case-2", "document_id": "doc-2", "label": None}]
    assert lookup(SHA_A, exclude_case_id="case-1") == [{"case_id": "case-2", "document_id": "doc-2", "label": None}]
    assert lookup("c" * 64) == []


def test_register_is_idempotent_and_keeps_registered_at_and_label(aws, hashes):
    register(SHA_A, "case-1", "doc-1")
    first = hashes.get_item(Key={"sha256": SHA_A, "case_document": "case-1#doc-1"})["Item"]
    assert set(first) == {"sha256", "case_document", "case_id", "document_id", "registered_at"}
    register(SHA_A, "case-1", "doc-1", "faktura")      # pipeline doplní štítek
    register(SHA_A, "case-1", "doc-1")                 # ingest ho znovu nesmaže
    register(SHA_A, "case-1", "doc-1")
    rows = hashes.scan()["Items"]
    assert len(rows) == 1
    assert rows[0]["label"] == "faktura" and rows[0]["registered_at"] == first["registered_at"]
    register(SHA_A, "case-1", "doc-1", "objednavka")   # nový štítek přepíše starý
    assert lookup(SHA_A)[0]["label"] == "objednavka"


def test_invalid_input(aws):
    for bad in ("", "abc", "G" * 64, "a" * 63):
        with pytest.raises(ValueError):
            lookup(bad)
        with pytest.raises(ValueError):
            register(bad, "c", "d")
    with pytest.raises(ValueError):
        register(SHA_A, "case#1", "d")
    assert lookup(SHA_A.upper()) == []  # velká písmena se normalizují


def test_missing_table_raises_hash_index_error_without_content(aws, monkeypatch):
    monkeypatch.setenv("DEDUP_HASHES_TABLE", "tabulka-ktera-neexistuje")
    with pytest.raises(HashIndexError) as caught:
        lookup(SHA_A)
    assert SHA_A not in str(caught.value) and "tabulka-ktera-neexistuje" not in str(caught.value)
    with pytest.raises(HashIndexError):
        register(SHA_A, "c", "d")


def test_corrupted_items_are_skipped_or_repaired_from_sort_key(aws, hashes):
    register(SHA_A, "case-1", "doc-1", "faktura")
    hashes.put_item(Item={"sha256": SHA_A, "case_document": "case-2#doc-2"})                       # bez case_id / document_id
    hashes.put_item(Item={"sha256": SHA_A, "case_document": "garbage"})                            # nejde rozebrat
    hashes.put_item(Item={"sha256": SHA_A, "case_document": "case-3#doc-3", "case_id": 5, "label": ["x"]})  # špatné typy
    assert lookup(SHA_A) == [{"case_id": "case-1", "document_id": "doc-1", "label": "faktura"},
                             {"case_id": "case-2", "document_id": "doc-2", "label": None},
                             {"case_id": "case-3", "document_id": "doc-3", "label": None}]


def test_concurrent_register_same_and_different_documents(aws, hashes):
    errors = []

    def worker(case, doc, label):
        try:
            for _ in range(3):
                register(SHA_A, case, doc, label)
        except Exception as error:  # noqa: BLE001
            errors.append(error)

    threads = [threading.Thread(target=worker, args=("case-same", "doc-same", "faktura" if n % 2 else None)) for n in range(12)]
    threads += [threading.Thread(target=worker, args=(f"case-{n}", f"doc-{n}", None)) for n in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    found = lookup(SHA_A)
    assert len(found) == 13 and len({(m["case_id"], m["document_id"]) for m in found}) == 13
    assert next(m for m in found if m["case_id"] == "case-same")["label"] == "faktura"  # štítek nezmizel


class Loader(yaml.SafeLoader):
    pass


Loader.add_multi_constructor("!", lambda loader, suffix, node: loader.construct_scalar(node) if isinstance(node, yaml.ScalarNode) else None)


def test_template_matches_what_code_expects():
    template = yaml.load((Path(__file__).parents[1] / "template.yaml").read_text(), Loader)
    resources = template["Resources"]
    assert list(resources) == ["ContentHashesTable"]  # nic než tabulka
    props = resources["ContentHashesTable"]["Properties"]
    assert props["TableName"] == HASHES == hashindex.DEFAULT_TABLE and props["BillingMode"] == "PAY_PER_REQUEST"
    assert [(k["AttributeName"], k["KeyType"]) for k in props["KeySchema"]] == [("sha256", "HASH"), (hashindex.SK, "RANGE")]
    assert {"Key": "project", "Value": "wonderfulkb"} in props["Tags"]
