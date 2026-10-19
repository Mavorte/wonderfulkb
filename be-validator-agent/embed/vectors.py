"""Zápis a čtení S3 Vectors (bucket wonderfulkb-vectors) podle validator-agent-storage.md."""
from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from . import clients, embeddings
from .chunking import chunk_text

INDEXES = {
    "text": "wonderfulkb-text",
    "image": "wonderfulkb-image",
    "signatures": "wonderfulkb-signatures",
}
PUT_BATCH = 500        # limit S3 Vectors na jedno put_vectors / delete_vectors
GET_BATCH = 100        # limit get_vectors
MAX_TOP_K = 100        # limit query_vectors


def index_name(index: str) -> str:
    """Přijme `text` / `image` / `signatures` i plný název `wonderfulkb-…`."""
    if index in INDEXES:
        return INDEXES[index]
    if index in INDEXES.values():
        return index
    raise ValueError(f"neznámý index {index!r}, očekáváno {sorted(INDEXES)}")


def _batches(items: Sequence, size: int) -> Iterable[Sequence]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _retry(fn):
    return clients.call_with_retry(fn)


def _meta(case_id: str, document_id: str, page: int, label: str | None, model: str,
          model_version: str, **extra) -> dict:
    meta = {"case_id": case_id, "document_id": document_id, "page": page,
            "verified": False, "model": model, "model_version": model_version, **extra}
    if label:  # S3 Vectors neumí null; chybějící štítek = klíč chybí
        meta["label"] = label
    return meta


def put_vectors(index: str, vectors: Sequence[dict], *, s3v=None) -> int:
    """Zapíše `[{key, vector, metadata}]` po dávkách do 500. Stejný klíč přepíše vektor (idempotentní)."""
    s3v = s3v or clients.s3vectors_client()
    name = index_name(index)
    for batch in _batches(list(vectors), PUT_BATCH):
        payload = [{"key": v["key"], "data": {"float32": [float(x) for x in v["vector"]]},
                    "metadata": v["metadata"]} for v in batch]
        _retry(lambda p=payload: s3v.put_vectors(vectorBucketName=clients.VECTOR_BUCKET,
                                                 indexName=name, vectors=p))
    return len(vectors)


def delete_vectors(index: str, keys: Sequence[str], *, s3v=None) -> int:
    s3v = s3v or clients.s3vectors_client()
    name = index_name(index)
    for batch in _batches(list(keys), PUT_BATCH):
        _retry(lambda b=list(batch): s3v.delete_vectors(vectorBucketName=clients.VECTOR_BUCKET,
                                                        indexName=name, keys=b))
    return len(keys)


def _remove_stale(index: str, document_id: str, keep: set[str], probe: list[float], s3v) -> list[str]:
    """Smaže klíče dokumentu, které nové zpracování už nevytvořilo (např. kratší text → méně částí).

    Dohledává dotazem s filtrem `document_id` (nejvýše 100 nejbližších), takže u dokumentu
    s víc než 100 vektory v indexu je úklid jen částečný.
    """
    resp = _retry(lambda: s3v.query_vectors(
        vectorBucketName=clients.VECTOR_BUCKET, indexName=index_name(index),
        queryVector={"float32": probe}, topK=MAX_TOP_K,
        filter={"document_id": {"$eq": document_id}}, returnMetadata=False, returnDistance=False))
    stale = [v["key"] for v in resp.get("vectors", []) if v["key"] not in keep]
    if stale:
        delete_vectors(index, stale, s3v=s3v)
    return stale


def write_document_vectors(case_id: str, document_id: str, text: str,
                           page_pngs: Sequence[bytes] | Mapping[int, bytes] | None,
                           label: str | None = None, *, bedrock=None, s3v=None,
                           cleanup_stale: bool = True) -> dict:
    """Rozdělí text na části, vloží části i stránky a zapíše je do indexů text a image.

    `page_pngs`: seznam PNG (první = strana 1) nebo `{číslo strany: PNG}`.
    Nejdřív se spočítají všechny embeddingy a až potom se cokoli zapíše, takže chyba Bedrocku
    nenechá dokument napůl zapsaný. Opakované volání přepíše stejné klíče; vektory jsou vždy
    zapsány s `verified=false` (i po novém zpracování dříve ověřeného dokumentu).
    Vrací `{"text": [klíče], "image": [klíče], "stale_removed": {...}}`.
    """
    chunks = chunk_text(text or "")
    pages = (dict(page_pngs) if isinstance(page_pngs, Mapping)
             else {i: png for i, png in enumerate(page_pngs or [], start=1)})

    tm, im = embeddings.text_model(), embeddings.image_model()
    chunk_vecs = embeddings.embed_texts([c.text for c in chunks], bedrock=bedrock)
    text_vecs = [{
        "key": f"{document_id}#t{c.index}",
        "vector": vec,
        "metadata": _meta(case_id, document_id, c.page_from, label, tm.model, tm.version,
                          chunk_id=c.chunk_id, page_from=c.page_from, page_to=c.page_to),
    } for c, vec in zip(chunks, chunk_vecs)]
    image_vecs = [{
        "key": f"{document_id}#p{n}",
        "vector": embeddings.embed_image(png, bedrock=bedrock),
        "metadata": _meta(case_id, document_id, n, label, im.model, im.version),
    } for n, png in sorted(pages.items())]

    s3v = s3v or clients.s3vectors_client()
    result: dict = {"text": [v["key"] for v in text_vecs], "image": [v["key"] for v in image_vecs],
                    "stale_removed": {}}
    for index, vecs in (("text", text_vecs), ("image", image_vecs)):
        if vecs:
            put_vectors(index, vecs, s3v=s3v)
        if cleanup_stale:
            probe = vecs[0]["vector"] if vecs else None
            if probe is None:  # prázdný výsledek: dotaz potřebuje nějaký vektor
                probe = [1.0] + [0.0] * (embeddings.DIMENSION - 1)
            result["stale_removed"][index] = _remove_stale(
                index, document_id, {v["key"] for v in vecs}, probe, s3v)
    return result


def write_signature_vectors(case_id: str, document_id: str, crops: Sequence[tuple[int, bytes]],
                            label: str | None = None, *, bedrock=None, s3v=None) -> list[str]:
    """Zapíše výřezy podpisů `[(strana, PNG), …]` jako `<document_id>#s<n>` (n od 0 podle pořadí)."""
    im = embeddings.image_model()
    vecs = [{
        "key": f"{document_id}#s{n}",
        "vector": embeddings.embed_image(png, bedrock=bedrock),
        "metadata": _meta(case_id, document_id, page, label, im.model, im.version),
    } for n, (page, png) in enumerate(crops)]
    if vecs:
        put_vectors("signatures", vecs, s3v=s3v)
    return [v["key"] for v in vecs]


def set_verified(index: str, keys: Sequence[str], verified: bool = True, label: str | None = None,
                 *, s3v=None) -> int:
    """Přepíše `verified` (a volitelně `label`) u existujících vektorů; vektor i ostatní metadata zůstanou.

    S3 Vectors neumí částečný update metadat, proto se vektor přečte a zapíše znovu.
    """
    s3v = s3v or clients.s3vectors_client()
    name = index_name(index)
    out: list[dict] = []
    for batch in _batches(list(keys), GET_BATCH):
        resp = _retry(lambda b=list(batch): s3v.get_vectors(
            vectorBucketName=clients.VECTOR_BUCKET, indexName=name, keys=b,
            returnData=True, returnMetadata=True))
        for v in resp.get("vectors", []):
            meta = dict(v.get("metadata") or {})
            meta["verified"] = bool(verified)
            if label:
                meta["label"] = label
            out.append({"key": v["key"], "vector": v["data"]["float32"], "metadata": meta})
    if out:
        put_vectors(index, out, s3v=s3v)
    return len(out)


def nearest_verified(vector: Sequence[float], index: str, top_k: int = 5, *,
                     case_id: str | None = None, exclude_document_id: str | None = None,
                     any_model: bool = False, s3v=None) -> list[dict]:
    """Nejbližší **ověřené** (`verified=true`) vektory; volitelně jen z jednoho `case_id`.

    Vrací `[{key, document_id, case_id, label, score, distance, metadata}]` od nejpodobnějšího;
    `score = 1 - distance` (cosine, 1 = shodné). V indexu text může být víc částí téhož dokumentu.
    Hledá se jen mezi vektory aktuálně nastaveného modelu indexu (`EMBED_TEXT_MODEL` /
    `EMBED_IMAGE_MODEL`), protože vektory různých modelů nejsou srovnatelné; `any_model=True` to vypne.
    """
    if not 1 <= top_k <= MAX_TOP_K:
        raise ValueError(f"top_k musí být 1 až {MAX_TOP_K}")
    conds: list[dict] = [{"verified": {"$eq": True}}]
    if not any_model:
        ref = embeddings.model_for_index(index)
        conds += [{"model": {"$eq": ref.model}}, {"model_version": {"$eq": ref.version}}]
    if case_id:
        conds.append({"case_id": {"$eq": case_id}})
    if exclude_document_id:
        conds.append({"document_id": {"$ne": exclude_document_id}})
    flt = conds[0] if len(conds) == 1 else {"$and": conds}

    s3v = s3v or clients.s3vectors_client()
    resp = _retry(lambda: s3v.query_vectors(
        vectorBucketName=clients.VECTOR_BUCKET, indexName=index_name(index),
        queryVector={"float32": [float(x) for x in vector]}, topK=top_k, filter=flt,
        returnMetadata=True, returnDistance=True))
    results = []
    for v in resp.get("vectors", []):
        meta = v.get("metadata") or {}
        dist = v.get("distance")
        results.append({"key": v["key"], "document_id": meta.get("document_id"),
                        "case_id": meta.get("case_id"), "label": meta.get("label"),
                        "score": None if dist is None else 1.0 - dist, "distance": dist,
                        "metadata": meta})
    return results
