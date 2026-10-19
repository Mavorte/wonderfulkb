import base64
import os

import pytest

from signature_privacy import DecryptionError, LocalKeyProvider, PrivacyError, SignatureContext, default_provider
from signature_privacy import keys


def test_data_keys_are_unique_and_unwrap(ctx):
    p = LocalKeyProvider.generate()
    k1, w1 = p.generate_data_key(ctx)
    k2, w2 = p.generate_data_key(ctx)
    assert len(k1) == 32 and k1 != k2 and w1 != w2
    assert p.decrypt_data_key(w1, ctx) == k1


def test_wrapped_key_bound_to_context(ctx):
    p = LocalKeyProvider.generate()
    _, w = p.generate_data_key(ctx)
    with pytest.raises(DecryptionError):
        p.decrypt_data_key(w, ctx._replace(signature_id="sig_02"))
    with pytest.raises(DecryptionError):
        p.decrypt_data_key(b"short", ctx)


def test_master_key_validation():
    with pytest.raises(PrivacyError):
        LocalKeyProvider(b"x" * 16)


def test_from_env(monkeypatch, ctx):
    key = os.urandom(32)
    monkeypatch.setenv("WKB_LOCAL_MASTER_KEY", base64.b64encode(key).decode())
    a, b = LocalKeyProvider.from_env(), LocalKeyProvider(key)
    k, w = a.generate_data_key(ctx)
    assert b.decrypt_data_key(w, ctx) == k
    monkeypatch.setenv("WKB_LOCAL_MASTER_KEY", "!!!")
    with pytest.raises(PrivacyError):
        LocalKeyProvider.from_env()
    monkeypatch.delenv("WKB_LOCAL_MASTER_KEY")
    with pytest.raises(PrivacyError):
        LocalKeyProvider.from_env()


def test_default_provider_requires_configuration(monkeypatch):
    monkeypatch.setattr(keys, "_default", None)
    monkeypatch.delenv("PRIVACY_KMS_KEY_ID", raising=False)
    monkeypatch.delenv("WKB_LOCAL_MASTER_KEY", raising=False)
    with pytest.raises(PrivacyError):
        default_provider()
