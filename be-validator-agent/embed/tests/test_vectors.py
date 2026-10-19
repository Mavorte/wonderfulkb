import pytest

from embed import (chunk_text, delete_vectors, nearest_verified, put_vectors, set_verified,
                   write_document_vectors, write_signature_vectors)
from conftest import png

TEXT = "\f".join(("Odstavec %d. " % i + "slovo " * 200 + "\n\n") * 4 for i in range(3))


def test_write_document_vectors_keys_and_metadata(bedrock, s3v):
    res = write_document_vectors("case-1", "doc-1", TEXT, [png(), png()], label="smlouva",
                                 bedrock=bedrock, s3v=s3v)
    n_chunks = len(chunk_text(TEXT))
    assert res["text"] == [f"doc-1#t{i}" for i in range(n_chunks)]
    assert res["image"] == ["doc-1#p1", "doc-1#p2"]
    m = s3v.store[("wonderfulkb-text", "doc-1#t0")]["metadata"]
    assert m == {"case_id": "case-1", "document_id": "doc-1", "page": 1, "verified": False,
                 "model": "amazon.titan-embed-text-v2:0", "model_version": "v2", "label": "smlouva",
                 "chunk_id": "c0", "page_from": 1, "page_to": m["page_to"]}
    assert "doc_id" not in m
    im = s3v.store[("wonderfulkb-image", "doc-1#p2")]["metadata"]
    assert im["page"] == 2 and im["model"] == "amazon.titan-embed-image-v1" and im["verified"] is False
    assert "chunk_id" not in im


def test_no_label_means_no_label_key(bedrock, s3v):
    write_document_vectors("c", "d", "Krátký text.", [], bedrock=bedrock, s3v=s3v)
    assert "label" not in s3v.store[("wonderfulkb-text", "d#t0")]["metadata"]


def test_page_pngs_dict_and_idempotent_rewrite(bedrock, s3v):
    write_document_vectors("c", "d", "Text.", {3: png()}, bedrock=bedrock, s3v=s3v)
    write_document_vectors("c", "d", "Text.", {3: png()}, bedrock=bedrock, s3v=s3v)
    keys = {k for (i, k) in s3v.store}
    assert keys == {"d#t0", "d#p3"}


def test_rewrite_with_shorter_text_removes_stale_chunks(bedrock, s3v):
    write_document_vectors("c", "d", TEXT, [], bedrock=bedrock, s3v=s3v)
    assert len([k for (i, k) in s3v.store if i == "wonderfulkb-text"]) > 1
    res = write_document_vectors("c", "d", "Jen krátký text.", [], bedrock=bedrock, s3v=s3v)
    assert [k for (i, k) in s3v.store if i == "wonderfulkb-text"] == ["d#t0"]
    assert res["stale_removed"]["text"]


def test_other_documents_not_touched_by_cleanup(bedrock, s3v):
    write_document_vectors("c", "other", "Cizí.", [png()], bedrock=bedrock, s3v=s3v)
    write_document_vectors("c", "d", "Moje.", [], bedrock=bedrock, s3v=s3v)
    assert ("wonderfulkb-text", "other#t0") in s3v.store and ("wonderfulkb-image", "other#p1") in s3v.store


def test_embedding_failure_writes_nothing(s3v):
    from conftest import FakeBedrock
    b = FakeBedrock(fail_first=0)
    orig = b.invoke_model
    state = {"n": 0}

    def flaky(modelId, body, **kw):
        state["n"] += 1
        if state["n"] == 3:
            raise ValueError("boom")
        return orig(modelId, body, **kw)

    b.invoke_model = flaky
    with pytest.raises(ValueError):
        write_document_vectors("c", "d", TEXT, [], bedrock=b, s3v=s3v)
    assert s3v.store == {}


def test_batches_of_at_most_500(s3v):
    vecs = [{"key": f"k{i}", "vector": [1.0] + [0.0] * 1023,
             "metadata": {"verified": False}} for i in range(1201)]
    assert put_vectors("text", vecs, s3v=s3v) == 1201
    assert s3v.put_sizes == [500, 500, 201]
    assert delete_vectors("text", [f"k{i}" for i in range(1201)], s3v=s3v) == 1201
    assert s3v.store == {}


def test_nearest_verified_filters(bedrock, s3v):
    write_document_vectors("A", "da", "Text a.", [], label="smlouva", bedrock=bedrock, s3v=s3v)
    write_document_vectors("B", "db", "Text b.", [], label="faktura", bedrock=bedrock, s3v=s3v)
    q = s3v.store[("wonderfulkb-text", "da#t0")]["data"]["float32"]
    assert nearest_verified(q, "text", 5, s3v=s3v) == []  # nic zatím není ověřeno

    set_verified("text", ["da#t0", "db#t0"], label=None, s3v=s3v)
    res = nearest_verified(q, "wonderfulkb-text", 5, s3v=s3v)
    assert [r["document_id"] for r in res][0] == "da"
    assert res[0]["score"] == pytest.approx(1.0) and res[0]["label"] == "smlouva"
    assert {r["document_id"] for r in nearest_verified(q, "text", 5, case_id="B", s3v=s3v)} == {"db"}
    assert {r["document_id"] for r in nearest_verified(q, "text", 5, exclude_document_id="da", s3v=s3v)} == {"db"}


def test_set_verified_keeps_vector_and_metadata(bedrock, s3v):
    write_document_vectors("A", "da", "Text.", [], label="x", bedrock=bedrock, s3v=s3v)
    before = s3v.store[("wonderfulkb-text", "da#t0")]
    vec = list(before["data"]["float32"])
    set_verified("text", ["da#t0"], label="smlouva", s3v=s3v)
    after = s3v.store[("wonderfulkb-text", "da#t0")]
    assert after["data"]["float32"] == vec
    assert after["metadata"]["verified"] is True and after["metadata"]["label"] == "smlouva"
    assert after["metadata"]["chunk_id"] == "c0"


def test_bad_arguments(s3v):
    with pytest.raises(ValueError):
        nearest_verified([0.0] * 1024, "text", 0, s3v=s3v)
    with pytest.raises(ValueError):
        nearest_verified([0.0] * 1024, "text", 101, s3v=s3v)
    with pytest.raises(ValueError):
        nearest_verified([0.0] * 1024, "nonsense", 3, s3v=s3v)


def test_signature_vectors(bedrock, s3v):
    keys = write_signature_vectors("c", "d", [(3, png(50, 20)), (3, png(60, 25))], bedrock=bedrock, s3v=s3v)
    assert keys == ["d#s0", "d#s1"]
    assert s3v.store[("wonderfulkb-signatures", "d#s1")]["metadata"]["page"] == 3


def test_model_goes_to_metadata_and_models_are_not_mixed(bedrock, s3v, monkeypatch):
    write_document_vectors("c", "titan-doc", "Text titan.", [png()], bedrock=bedrock, s3v=s3v)
    monkeypatch.setenv("EMBED_TEXT_MODEL", "cohere.embed-v4:0")
    monkeypatch.setenv("EMBED_IMAGE_MODEL", "cohere.embed-v4:0")
    write_document_vectors("c", "cohere-doc", "Text cohere.", [png()], bedrock=bedrock, s3v=s3v)
    m = s3v.store[("wonderfulkb-text", "cohere-doc#t0")]["metadata"]
    assert (m["model"], m["model_version"]) == ("cohere.embed-v4:0", "v4")
    assert s3v.store[("wonderfulkb-image", "cohere-doc#p1")]["metadata"]["model"] == "cohere.embed-v4:0"
    for idx, keys in (("text", ["titan-doc#t0", "cohere-doc#t0"]), ("image", ["titan-doc#p1", "cohere-doc#p1"])):
        set_verified(idx, keys, s3v=s3v)
    q = [1.0] + [0.0] * 1023
    assert {r["document_id"] for r in nearest_verified(q, "text", 5, s3v=s3v)} == {"cohere-doc"}
    assert {r["document_id"] for r in nearest_verified(q, "image", 5, s3v=s3v)} == {"cohere-doc"}
    assert {r["document_id"] for r in nearest_verified(q, "text", 5, any_model=True, s3v=s3v)} == {"titan-doc", "cohere-doc"}
    monkeypatch.delenv("EMBED_TEXT_MODEL")
    assert {r["document_id"] for r in nearest_verified(q, "text", 5, s3v=s3v)} == {"titan-doc"}
