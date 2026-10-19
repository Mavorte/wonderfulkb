import pytest

from signature_privacy import (DecryptionError, InvalidContext, LocalKeyProvider, SignatureContext, decrypt_image,
                               encrypt_image, is_encrypted_blob, set_default_provider)
from signature_privacy.blob import MAGIC, VERSION


def test_round_trip(sig_png, ctx, provider):
    blob = encrypt_image(sig_png, ctx, provider)
    assert is_encrypted_blob(blob)
    assert blob[:4] == MAGIC and blob[4] == VERSION
    assert sig_png not in blob and b"PNG" not in blob
    assert decrypt_image(blob, ctx, provider) == sig_png


def test_round_trip_with_dict_context_and_default_provider(sig_png, provider):
    set_default_provider(provider)
    try:
        c = {"case_id": "c", "document_id": "d", "signature_id": "s"}
        assert decrypt_image(encrypt_image(sig_png, c), c) == sig_png
    finally:
        set_default_provider(None)


def test_encryption_is_randomized(sig_png, ctx, provider):
    assert encrypt_image(sig_png, ctx, provider) != encrypt_image(sig_png, ctx, provider)


@pytest.mark.parametrize("field,value", [("case_id", "case-2"), ("document_id", "doc-2"), ("signature_id", "sig_02")])
def test_wrong_context_fails(sig_png, ctx, provider, field, value):
    blob = encrypt_image(sig_png, ctx, provider)
    with pytest.raises(DecryptionError):
        decrypt_image(blob, ctx._replace(**{field: value}), provider)


def test_wrong_key_fails(sig_png, ctx, provider):
    blob = encrypt_image(sig_png, ctx, provider)
    with pytest.raises(DecryptionError):
        decrypt_image(blob, ctx, LocalKeyProvider.generate())


@pytest.mark.parametrize("bad", [{}, {"case_id": "a", "document_id": "b"},
                                 {"case_id": "a", "document_id": "b", "signature_id": ""},
                                 {"case_id": "a", "document_id": "b", "signature_id": "c", "x": "y"},
                                 {"case_id": "a", "document_id": "b", "signature_id": 3}, None, "a"])
def test_invalid_context_rejected(sig_png, provider, bad):
    with pytest.raises(InvalidContext):
        encrypt_image(sig_png, bad, provider)


def test_every_corrupted_byte_fails(sig_png, ctx, provider):
    blob = bytearray(encrypt_image(sig_png[:300], ctx, provider))
    for i in range(len(blob)):
        bad = bytearray(blob)
        bad[i] ^= 0x01
        with pytest.raises(DecryptionError):
            decrypt_image(bytes(bad), ctx, provider)


@pytest.mark.parametrize("cut", [0, 1, 7, 8, 30, -1, -16])
def test_truncated_fails(sig_png, ctx, provider, cut):
    blob = encrypt_image(sig_png, ctx, provider)
    with pytest.raises(DecryptionError):
        decrypt_image(blob[:cut] if cut >= 0 else blob[:cut], ctx, provider)


def test_unknown_version_fails(sig_png, ctx, provider):
    blob = bytearray(encrypt_image(sig_png, ctx, provider))
    blob[4] = 2
    with pytest.raises(DecryptionError):
        decrypt_image(bytes(blob), ctx, provider)


def test_plain_png_is_not_a_valid_blob(sig_png, ctx, provider):
    assert not is_encrypted_blob(sig_png)
    with pytest.raises(DecryptionError):
        decrypt_image(sig_png, ctx, provider)


def test_errors_do_not_leak_secrets(sig_png, ctx, provider):
    blob = encrypt_image(sig_png, ctx, provider)
    with pytest.raises(DecryptionError) as e:
        decrypt_image(blob, ctx._replace(signature_id="sig_99"), provider)
    msg = str(e.value) + repr(provider)
    assert "sig_99" not in msg and "sig_01" not in msg
    assert "<skryto>" in repr(provider)
