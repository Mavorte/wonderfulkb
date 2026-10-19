"""Odkrytí podpisu: preview_url / reveal_path / crop_available, endpoint …/signatures/{id}/image, audit, KMS.
Spuštění: python3 -m pytest -q  (moto, LocalKeyProvider a mock KMS; živý KMS Decrypt v Lambdě tu ověřený není)."""
import base64
import json
import logging
import os
import sys
import urllib.parse

import boto3
import pytest
from moto import mock_aws

import app
import core
import crop_reveal
import fixtures
from signature_privacy import (KmsKeyProvider, LocalKeyProvider, SignatureContext, distorted_preview,
                               encrypt_image)

KEY = "fake-test-key-123"
PNG = b"\x89PNG\r\n\x1a\n"
AUDIT = "wonderfulkb.agent_api.audit"


@pytest.fixture(scope="module")
def env():
    with mock_aws():
        api, index, clients = fixtures.build(KEY)
        yield api, index, clients


def call(api, path, query=None, key=KEY, request=None):
    return core.handle("GET", "/v1" + path, query or {}, {"X-Api-Key": key} if key else {}, api=api, request=request)


def doc(index):
    c = next(c for c in index["cases"] if c["client"] == "Stavby Fišer a.s.")
    d = next(d for d in c["documents"] if d["title"].startswith("0_F"))
    return c["case_id"], d["document_id"]


def sig_path(cid, did, sid="sig_01"):
    return f"/cases/{cid}/documents/{did}/signatures/{sid}/image"


def audit_records(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == AUDIT]


@pytest.fixture
def swap(env):
    """Dočasně změní signatures.json a objekty výřezů; po testu vrátí původní stav."""
    api, index, clients = env
    cid, did = doc(index)
    prefix = f"cases/{cid}/analysis/{did}/"
    bucket = clients.cfg.bucket
    saved = {}

    class Swap:
        def __init__(self):
            self.cid, self.did, self.prefix = cid, did, prefix

        def get(self, key):
            return clients.s3.get_object(Bucket=bucket, Key=key)["Body"].read()

        def put(self, key, body):
            if key not in saved:
                try:
                    saved[key] = self.get(key)
                except clients.s3.exceptions.NoSuchKey:
                    saved[key] = None
            clients.s3.put_object(Bucket=bucket, Key=key, Body=body)

        def delete(self, key):
            if key not in saved:
                saved[key] = self.get(key)
            clients.s3.delete_object(Bucket=bucket, Key=key)

        def edit_sigs(self, fn):
            key = prefix + "signatures.json"
            doc_ = json.loads(self.get(key))
            fn(doc_["signatures"])
            self.put(key, json.dumps(doc_).encode())

    yield Swap()
    for k, v in saved.items():
        if v is None:
            clients.s3.delete_object(Bucket=bucket, Key=k)
        else:
            clients.s3.put_object(Bucket=bucket, Key=k, Body=v)


# ---- volání 3: bez čitelného odkazu -------------------------------------------------------------

def test_signatures_have_preview_reveal_path_and_no_readable_url(env):
    api, index, clients = env
    cid, did = doc(index)
    st, b = call(api, f"/cases/{cid}/documents/{did}/signatures")
    assert st == 200 and len(b["signatures"]) == 2
    for s in b["signatures"]:
        assert s["crop_available"] is True
        assert s["reveal_path"] == sig_path(cid, did, s["signature_id"])
        assert "crop_url" not in s
        u = urllib.parse.urlparse(s["preview_url"])
        q = urllib.parse.parse_qs(u.query)
        assert q["X-Amz-Expires"] == ["300"] and u.path.endswith(f"{s['signature_id']}.preview.png")
        assert not u.path.endswith(".enc") and not u.path.endswith("sig_01.png")
        assert not {"crop_s3_key", "crop_encrypted", "crop_source", "preview_s3_key"} & set(s)
    assert ".png.enc" not in json.dumps(b)


def test_preview_is_distorted_object_not_the_crop(env):
    """Odkaz míří na samostatný zkreslený objekt, ne na výřez; náhled není shodný s dešifrovaným PNG."""
    api, index, clients = env
    cid, did = doc(index)
    s = call(api, f"/cases/{cid}/documents/{did}/signatures")[1]["signatures"][0]
    key = urllib.parse.unquote(urllib.parse.urlparse(s["preview_url"]).path.lstrip("/"))
    preview = clients.s3.get_object(Bucket=clients.cfg.bucket, Key=key)["Body"].read()
    revealed = call(api, s["reveal_path"])[1].data
    assert preview.startswith(PNG) and revealed.startswith(PNG) and preview != revealed


def test_no_preview_means_null_preview_url(env, swap):
    api, index, _ = env
    swap.delete(swap.prefix + "signatures/sig_01.preview.png")
    s = call(api, f"/cases/{swap.cid}/documents/{swap.did}/signatures")[1]["signatures"][0]
    assert s["preview_url"] is None and s["crop_available"] is True


def test_legacy_plain_crop_gives_no_readable_link_by_default(env, swap):
    """Starý signatures.json bez crop_s3_key/crop_encrypted a čitelný .png: žádný odkaz na něj."""
    api, index, clients = env
    p = swap.prefix + "signatures/"
    swap.put(p + "sig_01.png", PNG + b"readable-legacy")
    swap.delete(p + "sig_01.png.enc")
    swap.edit_sigs(lambda sigs: [s.pop(k, None) for s in sigs for k in ("crop_s3_key", "crop_encrypted")])
    st, b = call(api, f"/cases/{swap.cid}/documents/{swap.did}/signatures")
    s = b["signatures"][0]
    assert st == 200 and s["crop_available"] is False and "crop_url" not in s
    assert s["preview_url"] is not None  # preview existuje, ten smí
    assert "sig_01.png?" not in json.dumps(b) and "readable-legacy" not in json.dumps(b)


def test_legacy_flag_and_compat_flag(env, swap, monkeypatch):
    api, index, clients = env
    p = swap.prefix + "signatures/"
    swap.put(p + "sig_01.png", PNG + b"x")
    swap.delete(p + "sig_01.png.enc")
    swap.edit_sigs(lambda sigs: [s.pop(k, None) for s in sigs for k in ("crop_s3_key", "crop_encrypted")])
    url = f"/cases/{swap.cid}/documents/{swap.did}/signatures"
    monkeypatch.setattr(clients.cfg, "crop_url_compat", True)
    sigs = call(api, url)[1]["signatures"]
    assert all(s["crop_url"] is None for s in sigs)  # klíč zůstává, hodnota ne
    monkeypatch.setattr(clients.cfg, "legacy_plain_crop_url", True)
    sigs = {s["signature_id"]: s for s in call(api, url)[1]["signatures"]}
    assert "X-Amz-Signature" in sigs["sig_01"]["crop_url"] and sigs["sig_01"]["crop_available"] is False
    assert sigs["sig_02"]["crop_url"] is None  # šifrovaný výřez čitelný odkaz nikdy nemá


def test_encrypted_crop_never_gets_plain_url_even_with_flag(env, monkeypatch):
    api, index, clients = env
    cid, did = doc(index)
    monkeypatch.setattr(clients.cfg, "legacy_plain_crop_url", True)
    assert all(s["crop_url"] is None for s in call(api, f"/cases/{cid}/documents/{did}/signatures")[1]["signatures"])


def test_crop_key_outside_document_prefix_is_ignored(env, swap):
    api, index, clients = env
    other = "cases/other/analysis/zzz/signatures/sig_01.png.enc"
    swap.put(other, b"WKBS-whatever")
    swap.edit_sigs(lambda sigs: sigs[0].update(crop_s3_key=other))
    s = call(api, f"/cases/{swap.cid}/documents/{swap.did}/signatures")[1]["signatures"][0]
    assert s["crop_available"] is True  # cizí klíč se ignoruje, platí konvenční klíč téhož dokumentu
    st, body = call(api, sig_path(swap.cid, swap.did))
    assert st == 200 and b"WKBS" not in body.data  # a cizí objekt se nečetl (jeho dešifrování by dalo 500)
    swap.delete(swap.prefix + "signatures/sig_01.png.enc")
    assert call(api, sig_path(swap.cid, swap.did))[0] == 404  # bez vlastního výřezu cizí objekt nepomůže
    clients.s3.delete_object(Bucket=clients.cfg.bucket, Key=other)


# ---- endpoint odkrytí ----------------------------------------------------------------------------------

def test_reveal_returns_png_with_no_store(env, caplog):
    api, index, _ = env
    cid, did = doc(index)
    caplog.set_level(logging.INFO)
    st, body = call(api, sig_path(cid, did))
    assert st == 200 and isinstance(body, core.Binary) and body.data.startswith(PNG)
    assert body.content_type == "image/png"
    assert body.headers["Cache-Control"] == "no-store" and body.headers["Content-Disposition"] == "inline"


def test_reveal_matches_original_crop_bytes(env):
    api, index, _ = env
    cid, did = doc(index)
    import importlib.util
    spec = importlib.util.spec_from_file_location("mock_seed", fixtures.SEED_PATH)
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    st = seed.Store()
    sig = next(s for (c, d), x in st.docs.items() if d == did for s in x.get("_sigs", []) if s["signature_id"] == "sig_01")
    assert call(api, sig_path(cid, did))[1].data == seed.signature_png(sig["_seed"])


def test_reveal_requires_api_key(env):
    api, index, _ = env
    cid, did = doc(index)
    for k in (None, ""):
        assert call(api, sig_path(cid, did), key=k) == (401, {"error": "Chybí API klíč"})
    assert call(api, sig_path(cid, did), key="wrong") == (403, {"error": "Špatný API klíč"})


def test_reveal_404_unknown_signature_document_case(env):
    api, index, _ = env
    cid, did = doc(index)
    assert call(api, sig_path(cid, did, "sig_99"))[0] == 404
    assert call(api, sig_path(cid, "neexistuje"))[0] == 404
    assert call(api, sig_path("neexistuje", did))[0] == 404
    c2 = next(c for c in index["cases"] if c["client"] == "Solom Rec s.r.o.")
    d2 = next(d for d in c2["documents"] if d["processing_status"] == "processing")
    assert call(api, sig_path(c2["case_id"], d2["document_id"]))[0] == 404  # nezpracovaný dokument
    assert call(api, f"/cases/{cid}/documents/{did}/signatures/..%2Fsig_01/image")[0] in (400, 404)
    assert call(api, f"/cases/{cid}/documents/{did}/signatures/%2E%2E/image")[0] == 400
    assert call(api, sig_path(cid, did), None)[0] == 200  # query se ignoruje


def test_reveal_404_when_crop_object_missing(env, swap):
    api, index, _ = env
    swap.delete(swap.prefix + "signatures/sig_01.png.enc")
    assert call(api, sig_path(swap.cid, swap.did)) == (404, {"error": "Výřez podpisu neexistuje"})


def test_reveal_409_for_unmigrated_plain_crop_never_readable(env, swap, caplog):
    api, index, _ = env
    p = swap.prefix + "signatures/"
    swap.put(p + "sig_01.png", PNG + b"readable-legacy")
    swap.delete(p + "sig_01.png.enc")
    swap.edit_sigs(lambda sigs: [s.pop(k, None) for s in sigs for k in ("crop_s3_key", "crop_encrypted")])
    caplog.set_level(logging.INFO)
    st, body = call(api, sig_path(swap.cid, swap.did))
    assert st == 409 and isinstance(body, dict) and "readable-legacy" not in json.dumps(body)
    assert audit_records(caplog)[-1]["outcome"] == "not_encrypted"


def test_reveal_409_when_enc_key_holds_readable_png(env, swap):
    """crop_s3_key ukazuje na .enc, ale objekt je čitelný PNG (zápis selhal nebo se přepsal): nevrátit ho."""
    api, index, _ = env
    swap.put(swap.prefix + "signatures/sig_01.png.enc", PNG + b"readable")
    st, body = call(api, sig_path(swap.cid, swap.did))
    assert st == 409 and isinstance(body, dict)


def test_reveal_wrong_context_fails_and_is_audited_as_denied(env, swap, caplog):
    """Blok zašifrovaný pro jiný podpis (podstrčený na cizí místo) se neodkryje."""
    api, index, clients = env
    other = swap.get(swap.prefix + "signatures/sig_02.png.enc")
    swap.put(swap.prefix + "signatures/sig_01.png.enc", other)
    caplog.set_level(logging.INFO)
    st, body = call(api, sig_path(swap.cid, swap.did))
    assert st == 500 and body == {"error": "Odkrytí výřezu selhalo"}
    assert audit_records(caplog)[-1]["outcome"] == "denied"


def test_reveal_crop_source_decrypts_with_original_context(env, swap):
    """Výřez zašifrovaný pod jiným podpisem (migrace, přesun) se odkryje s `crop_source`, bez něj ne."""
    api, index, clients = env
    src = {"case_id": "old-case", "document_id": "old-doc", "signature_id": "sig_07"}
    png = PNG + b"moved-crop"
    blob = encrypt_image(png, SignatureContext(**src), clients.key_provider)
    key = swap.prefix + "signatures/sig_01.png.enc"
    swap.put(key, blob)
    assert call(api, sig_path(swap.cid, swap.did))[0] == 500  # bez crop_source: špatný kontext
    swap.edit_sigs(lambda sigs: sigs[0].update(crop_s3_key=key, crop_encrypted=True, crop_source=src))
    st, body = call(api, sig_path(swap.cid, swap.did))
    assert st == 200 and body.data == png
    s = call(api, f"/cases/{swap.cid}/documents/{swap.did}/signatures")[1]["signatures"][0]
    assert "crop_source" not in s and s["crop_available"] is True
    for bad in ({"case_id": "a"}, "x", {**src, "extra": "1"}, {**src, "signature_id": ""}):
        swap.edit_sigs(lambda sigs, bad=bad: sigs[0].update(crop_source=bad))
        assert call(api, sig_path(swap.cid, swap.did))[0] == 500


def test_reveal_crop_source_cannot_widen_the_object_key(env, swap):
    """crop_source mění jen kontext dešifrování, nikdy klíč objektu: cizí objekt zůstává nedostupný."""
    api, index, clients = env
    ctx = SignatureContext("other", "zzz", "sig_01")
    other = "cases/other/analysis/zzz/signatures/sig_01.png.enc"
    swap.put(other, encrypt_image(PNG + b"alien", ctx, clients.key_provider))
    swap.edit_sigs(lambda sigs: sigs[0].update(crop_s3_key=other, crop_source=ctx._asdict()))
    st, body = call(api, sig_path(swap.cid, swap.did))
    assert st == 500 and isinstance(body, dict)  # cizí klíč se ignoruje; vlastní blok s cizím kontextem nejde odkrýt
    swap.delete(swap.prefix + "signatures/sig_01.png.enc")
    assert call(api, sig_path(swap.cid, swap.did))[0] == 404  # a cizí objekt nikdy nepomůže
    clients.s3.delete_object(Bucket=clients.cfg.bucket, Key=other)


def test_reveal_corrupted_blob_is_denied_without_detail(env, swap):
    api, index, _ = env
    key = swap.prefix + "signatures/sig_01.png.enc"
    blob = bytearray(swap.get(key))
    blob[-5] ^= 0xFF
    swap.put(key, bytes(blob))
    st, body = call(api, sig_path(swap.cid, swap.did))
    assert st == 500 and body == {"error": "Odkrytí výřezu selhalo"}


def test_reveal_signatures_json_unreadable_is_500(env, swap):
    api, index, _ = env
    swap.put(swap.prefix + "signatures.json", b"{broken")
    assert call(api, sig_path(swap.cid, swap.did))[0] == 500


# ---- audit ---------------------------------------------------------------------------------------------

def test_audit_record_has_who_when_what_and_no_secret_or_image(env, caplog):
    api, index, _ = env
    cid, did = doc(index)
    caplog.set_level(logging.DEBUG)
    st, body = call(api, sig_path(cid, did), request={"request_id": "req-1"})
    assert st == 200
    recs = audit_records(caplog)
    assert len(recs) == 1
    r = recs[0]
    assert r["event"] == "signature_reveal" and r["outcome"] == "revealed"
    assert (r["case_id"], r["document_id"], r["signature_id"]) == (cid, did, "sig_01")
    assert r["request_id"] == "req-1" and r["ts"].endswith("Z")
    assert r["caller"].startswith("fp:") and len(r["caller"]) == 15
    text = caplog.text
    assert KEY not in text and KEY[:8] not in text  # hodnota klíče nikde v logu
    assert base64.b64encode(body.data[:24]).decode() not in text and "PNG" not in text
    assert len(r) == 8  # právě tato pole, nic dalšího (obsah, klíč)


def test_audit_caller_prefers_api_key_id_and_distinguishes_keys(env, caplog, monkeypatch):
    api, index, _ = env
    cid, did = doc(index)
    caplog.set_level(logging.INFO)
    call(api, sig_path(cid, did), request={"api_key_id": "abc123"})
    assert audit_records(caplog)[-1]["caller"] == "abc123"
    assert core._caller({}, "k1") != core._caller({}, "k2") and core._caller({}, None) == "unknown"


def test_audit_covers_not_found_and_failed_auth_is_not_a_reveal(env, caplog):
    api, index, _ = env
    cid, did = doc(index)
    caplog.set_level(logging.INFO)
    call(api, sig_path(cid, did, "sig_99"))
    assert audit_records(caplog)[-1]["outcome"] == "not_found"
    n = len(audit_records(caplog))
    call(api, sig_path(cid, did), key="wrong")
    call(api, sig_path(cid, did, "bad id"))  # neplatný identifikátor se neloguje
    assert len(audit_records(caplog)) == n


def test_audit_survives_unexpected_error(env, caplog, monkeypatch):
    api, index, clients = env
    cid, did = doc(index)
    monkeypatch.setattr(clients, "_ddb", type("B", (), {"__getattr__": lambda s, n: (_ for _ in ()).throw(RuntimeError("x"))})())
    caplog.set_level(logging.INFO)
    assert call(api, sig_path(cid, did))[0] == 500
    assert audit_records(caplog)[-1]["outcome"] == "error"


# ---- Lambda adaptér ------------------------------------------------------------------------------------

def test_lambda_adapter_returns_base64_png_with_headers(env, monkeypatch):
    api, index, _ = env
    cid, did = doc(index)
    monkeypatch.setattr(core, "_default", api)
    ev = {"rawPath": "/v1" + sig_path(cid, did), "headers": {"x-api-key": KEY},
          "requestContext": {"requestId": "r-9", "http": {"method": "GET"}}}
    r = app.handler(ev)
    assert r["statusCode"] == 200 and r["isBase64Encoded"] is True
    assert base64.b64decode(r["body"]).startswith(PNG)
    assert r["headers"]["Content-Type"] == "image/png" and r["headers"]["Cache-Control"] == "no-store"
    assert r["headers"]["Content-Disposition"] == "inline"
    ev["headers"] = {"x-api-key": "wrong"}
    r = app.handler(ev)
    assert r["statusCode"] == 403 and r["headers"]["Content-Type"].startswith("application/json")
    ev["headers"] = {}
    r = app.handler(ev)
    assert r["statusCode"] == 401 and r["headers"]["Content-Type"].startswith("application/json")


# ---- šifrování: shoda s knihovnou signature_privacy a s KMS ----------------------------------------

def test_blob_from_library_is_readable_by_api_decryptor_and_context_is_enforced():
    p = LocalKeyProvider.generate()
    ctx = SignatureContext("c", "d", "sig_01")
    blob = encrypt_image(PNG + b"abc", ctx, p)
    assert crop_reveal.decrypt_blob(blob, ctx._asdict(), p) == PNG + b"abc"
    for bad in (ctx._replace(case_id="x"), ctx._replace(document_id="x"), ctx._replace(signature_id="x")):
        with pytest.raises(crop_reveal.DecryptionError):
            crop_reveal.decrypt_blob(blob, bad._asdict(), p)
    with pytest.raises(crop_reveal.DecryptionError):
        crop_reveal.decrypt_blob(blob, ctx._asdict(), LocalKeyProvider.generate())
    for i in range(0, len(blob), 7):  # poškození kteréhokoli bajtu
        b = bytearray(blob)
        b[i] ^= 1
        with pytest.raises(crop_reveal.DecryptionError):
            crop_reveal.decrypt_blob(bytes(b), ctx._asdict(), p)


def test_kms_decryptor_with_mock_kms_roundtrip_and_context():
    """Mock KMS (moto): blok zašifrovaný KmsKeyProvider z knihovny se odkryje KmsDecryptor; jiný kontext nebo
    jiný klíč KMS selže. Skutečný KMS Decrypt z Lambdy tímhle ověřený není."""
    with mock_aws():
        kms = boto3.client("kms", region_name="eu-central-1")
        k1 = kms.create_key()["KeyMetadata"]["KeyId"]
        k2 = kms.create_key()["KeyMetadata"]["KeyId"]
        ctx = SignatureContext("c", "d", "sig_01")
        blob = encrypt_image(PNG + b"zzz", ctx, KmsKeyProvider(k1, client=kms))
        good = crop_reveal.KmsDecryptor(kms, k1)
        assert crop_reveal.decrypt_blob(blob, ctx._asdict(), good) == PNG + b"zzz"
        with pytest.raises(crop_reveal.DecryptionError):
            crop_reveal.decrypt_blob(blob, ctx._replace(signature_id="sig_02")._asdict(), good)
        with pytest.raises(crop_reveal.DecryptionError):
            crop_reveal.decrypt_blob(blob, ctx._asdict(), crop_reveal.KmsDecryptor(kms, k2))


def test_default_provider_is_kms_decryptor_with_configured_alias(env, monkeypatch):
    api, index, clients = env
    fresh = core.Clients(core.Config({"API_KEY": KEY, "PRIVACY_KMS_KEY_ID": "alias/wonderfulkb-signatures"}),
                         kms=object())
    p = fresh.key_provider
    assert isinstance(p, crop_reveal.KmsDecryptor) and p.key_id == "alias/wonderfulkb-signatures"
    assert core.Config({}).kms_key_id == "alias/wonderfulkb-signatures"
    assert core.Config({}).legacy_plain_crop_url is False and core.Config({}).crop_url_compat is False
