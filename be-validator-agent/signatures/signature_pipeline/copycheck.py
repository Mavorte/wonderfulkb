"""Step 4: suspicion of a copied signature, across the documents of one case.

Real signatures of one person always differ a little; an (almost) identical stroke pattern in several
documents suggests a pasted image. Two stages: perceptual hash finds candidates, the pixel comparison of
ink masks confirms. Neither says anything about authenticity.
"""
from .imaging import hamming, mask_similarity

HAMMING_MAX = 8       # of 64 bits
PIXEL_MIN = 0.90      # Dice coefficient of ink masks
ASPECT_TOLERANCE = 0.12


def compare(a, b):
    """Similarity 0..1 when `a` and `b` look like the same pixels, else None."""
    if not a.phash or not b.phash or a.mask is None or b.mask is None:
        return None
    if hamming(a.phash, b.phash) > HAMMING_MAX:
        return None
    if abs(a.aspect - b.aspect) / max(a.aspect, b.aspect) > ASPECT_TOLERANCE:
        return None
    score = mask_similarity(a.mask, b.mask)
    return score if score >= PIXEL_MIN else None


def mark_copies(documents):
    """documents: {document_id: [Signature]}. Fills `copy_suspicion` of every signature in place."""
    ids = list(documents)
    for doc_id in ids:
        for sig in documents[doc_id]:
            matches = []
            for other_id in ids:
                if other_id == doc_id:
                    continue
                for other in documents[other_id]:
                    score = compare(sig, other)
                    if score is not None:
                        matches.append({"signature_id": other.signature_id, "document_id": other_id,
                                        "score": round(score, 3)})
            matches.sort(key=lambda m: -m["score"])
            sig.copy_suspicion = {"level": "suspected" if matches else "none", "matches": matches}
