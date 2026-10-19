"""Ověření nasazeného API třemi GET voláními (+ seznam a chybové případy). API klíč čte ze Secrets Manageru
(profil z AWS_PROFILE) a nikde ho nevypisuje.

    AWS_PROFILE=hackathon python3 verify_deployed.py https://<id>.execute-api.eu-central-1.amazonaws.com/v1 <case_id> [<document_id>]

Bez document_id vezme první `completed`/`partial` dokument ze seznamu. Vypisuje stavy a stručné shrnutí odpovědí.
"""
import json
import sys
import urllib.error
import urllib.request

import boto3


def main(base, case_id, doc_id=None):
    key = boto3.client("secretsmanager", region_name="eu-central-1").get_secret_value(
        SecretId="wonderfulkb/ingest-api-key")["SecretString"].strip()
    fails = 0

    def get(path, k=key):
        req = urllib.request.Request(base.rstrip("/") + path, headers={"x-api-key": k} if k else {})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def show(label, want, got, summary=""):
        nonlocal fails
        ok = got == want
        fails += not ok
        print(("OK   " if ok else "FAIL ") + f"{label}: {got}" + (f"  {summary}" if summary else ""))

    st, b = get("/healthz", None)
    show("healthz bez klíče", 200, st)
    st, b = get(f"/cases/{case_id}/documents", "spatny-klic")
    show("špatný klíč", 403, st)
    st, b = get(f"/cases/{case_id}/documents")
    show("seznam dokumentů", 200, st, f"{len(b.get('documents', []))} dokumentů" if st == 200 else str(b))
    if st != 200:
        sys.exit(1)
    if not doc_id:
        ready = [d for d in b["documents"] if d["processing_status"] in ("completed", "partial")]
        if not ready:
            print("Žádný zpracovaný dokument, volání 1 až 3 nelze ověřit.")
            sys.exit(1)
        doc_id = ready[0]["document_id"]
    base_doc = f"/cases/{case_id}/documents/{doc_id}"
    st, b = get(base_doc)
    show("volání 1: dokument", 200, st, f"label={b.get('label')} text={len(b.get('text', ''))} znaků" if st == 200 else str(b))
    st, b = get(base_doc + "/vectors?include_values=false&similar_to_verified=3")
    show("volání 2: vektory", 200, st, f"text={len(b.get('text_vectors', []))} obraz={len(b.get('image_vectors', []))} "
         f"neighbors={len(b.get('neighbors', []))}" if st == 200 else str(b))
    st, b = get(base_doc + "/signatures?match_client=true&include_vectors=false")
    show("volání 3: podpisy", 200, st, f"{len(b.get('signatures', []))} podpisů" if st == 200 else str(b))
    show("neexistující dokument", 404, get(f"/cases/{case_id}/documents/neexistuje")[0])
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(*sys.argv[1:4])
