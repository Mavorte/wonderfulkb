"""Kopie vektorů dokumentu v S3 Vectors pod nové klíče: bez volání Bedrocku.

Klíče podle kontraktu: `<document_id>#t<i>` (text, od 0), `#p<strana>` (obraz, od 1), `#s<n>` (podpisy, od 0).
Metadata se zkopírují a `case_id` / `document_id` se nahradí novými, `verified` je vždy `false` a `label` se nastaví
na štítek nového dokumentu (S3 Vectors neumí null: bez štítku klíč `label` chybí)."""
from __future__ import annotations

import os

BUCKET = os.environ.get("DEDUP_VECTOR_BUCKET", "wonderfulkb-vectors")
INDEXES = {"text": "wonderfulkb-text", "image": "wonderfulkb-image", "signatures": "wonderfulkb-signatures"}
GET_BATCH = 100
PUT_BATCH = 500


class VectorsUnavailable(RuntimeError):
    """Vektory původního dokumentu nejsou kompletní (chybí strana, žádný textový vektor): znovupoužít nejde."""


def s3vectors_client():
    import boto3
    return boto3.client("s3vectors", region_name=os.environ.get("AWS_DEFAULT_REGION") or "eu-central-1")


def _get(s3v, index, keys):
    out = []
    for i in range(0, len(keys), GET_BATCH):
        reply = s3v.get_vectors(vectorBucketName=BUCKET, indexName=INDEXES[index], keys=keys[i:i + GET_BATCH],
                                returnData=True, returnMetadata=True)
        out += reply.get("vectors", [])
    return out


def _run(s3v, index, prefix, start):
    """Souvislá řada `<document_id>#<prefix><start>`, `…<start+1>` … po blocích, dokud blok není neúplný."""
    found, number = [], start
    while True:
        keys = [f"{prefix}{i}" for i in range(number, number + GET_BATCH)]
        got = _get(s3v, index, keys)
        found += got
        if len(got) < GET_BATCH:
            return found
        number += GET_BATCH


def read_document_vectors(document_id: str, page_count: int, *, with_text: bool = True, with_images: bool = True,
                          with_signatures: bool = True, s3v=None) -> dict:
    """Vektory původního dokumentu `{"text": [...], "image": [...], "signatures": [...]}` (prvky `{key, data, metadata}`).
    Vyvolá `VectorsUnavailable`, když neodpovídají textu a stranám (každá strana má obrazový vektor, text aspoň jednu
    část): neúplná sada by dala novému dokumentu méně vektorů, než by mu dalo zpracování."""
    s3v = s3v or s3vectors_client()
    out = {"text": [], "image": [], "signatures": []}
    if with_text:
        out["text"] = _run(s3v, "text", f"{document_id}#t", 0)
        if not out["text"]:
            raise VectorsUnavailable("původní dokument nemá textové vektory")
    if with_images and page_count:
        keys = [f"{document_id}#p{n}" for n in range(1, page_count + 1)]
        out["image"] = _get(s3v, "image", keys)
        if len(out["image"]) != page_count:
            raise VectorsUnavailable(f"původní dokument má {len(out['image'])} z {page_count} obrazových vektorů")
    if with_signatures:
        out["signatures"] = _run(s3v, "signatures", f"{document_id}#s", 0)
    return out


def rekey(vectors: dict, from_document_id: str, case_id: str, document_id: str, label: str | None) -> dict:
    """Stejná sada s novými klíči a metadaty nového dokumentu (zdroj se nemění)."""
    out = {}
    for index, items in vectors.items():
        out[index] = []
        for item in items:
            meta = dict(item.get("metadata") or {})
            meta.update(case_id=case_id, document_id=document_id, verified=False)
            meta.pop("label", None)
            if label:
                meta["label"] = label
            suffix = item["key"][len(from_document_id):]
            if item["key"][:len(from_document_id)] != from_document_id or not suffix.startswith("#"):
                raise ValueError("neočekávaný klíč vektoru")
            out[index].append({"key": document_id + suffix, "data": {"float32": list(item["data"]["float32"])},
                               "metadata": meta})
    return out


def write_vectors(vectors: dict, *, s3v=None) -> int:
    """Zapíše sadu po dávkách do 500; stejný klíč přepíše vektor (idempotentní). Vrací počet vektorů."""
    s3v = s3v or s3vectors_client()
    total = 0
    for index, items in vectors.items():
        for i in range(0, len(items), PUT_BATCH):
            batch = items[i:i + PUT_BATCH]
            s3v.put_vectors(vectorBucketName=BUCKET, indexName=INDEXES[index], vectors=batch)
            total += len(batch)
    return total


def copy_document_vectors(src_document_id, dst_case_id, dst_document_id, page_count, label, *, with_text=True,
                          with_images=True, with_signatures=True, s3v=None) -> dict:
    """Načte vektory původního dokumentu a zapíše je pod nové klíče. Vrací počty `{"text": n, "image": n, "signatures": n}`."""
    s3v = s3v or s3vectors_client()
    source = read_document_vectors(src_document_id, page_count, with_text=with_text, with_images=with_images,
                                   with_signatures=with_signatures, s3v=s3v)
    moved = rekey(source, src_document_id, dst_case_id, dst_document_id, label)
    write_vectors(moved, s3v=s3v)
    return {index: len(items) for index, items in moved.items()}
